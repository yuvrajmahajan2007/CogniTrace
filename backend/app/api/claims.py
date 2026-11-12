from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, joinedload
from ..db import SessionLocal
from .. import models
from ..schemas import claim as claim_schema
from ..services import claim_extractor

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _get_citation_context(db: Session, cit: models.Citation) -> dict:
    chunk = (
        db.query(models.EvidenceChunk)
        .filter(models.EvidenceChunk.id == cit.evidence_chunk_id)
        .first()
    )
    if not chunk:
        return {"surrounding_context": cit.excerpt}
    surrounding = chunk.text
    if getattr(chunk, "source_type", "document") == "document":
        nxt = (
            db.query(models.EvidenceChunk)
            .filter(
                models.EvidenceChunk.file_id == chunk.file_id,
                models.EvidenceChunk.chunk_index == chunk.chunk_index + 1,
            )
            .first()
        )
        if nxt and nxt.page_number == chunk.page_number:
            surrounding = f"{chunk.text}\n{nxt.text[:400]}"
    return {
        "surrounding_context": surrounding,
        "source_type": getattr(chunk, "source_type", "document"),
        "record_id": getattr(chunk, "record_id", None),
        "author": getattr(chunk, "author", None),
        "record_timestamp": getattr(chunk, "record_timestamp", None),
    }


def _serialize_claim(c: models.Claim, db: Optional[Session] = None) -> dict:
    citations_out = []
    for cit in c.citations:
        cit_dict = claim_schema.CitationSchema.model_validate(cit).model_dump()
        if db is not None:
            cit_dict.update(_get_citation_context(db, cit))
        else:
            cit_dict["surrounding_context"] = cit.excerpt
        citations_out.append(cit_dict)

    return {
        "id": c.id,
        "claim_text": c.claim_text,
        "claim_type": c.claim_type.value if hasattr(c.claim_type, "value") else str(c.claim_type),
        "status": c.status.value if hasattr(c.status, "value") else str(c.status),
        "source_file_id": c.source_file_id,
        "source_filename": c.source_filename,
        "extraction_method": c.extraction_method,
        "insufficient_evidence": c.insufficient_evidence,
        "created_at": c.created_at,
        "updated_at": c.updated_at,
        "citations": citations_out,
        "review_history": [
            claim_schema.ReviewHistorySchema.model_validate(rh) for rh in c.review_history
        ],
    }


@router.post("/generate", response_model=claim_schema.ClaimGenerateResponse)
def generate_candidate_claims(
    payload: Optional[claim_schema.ClaimGenerateRequest] = None,
    db: Session = Depends(get_db),
):
    req = payload or claim_schema.ClaimGenerateRequest()
    result = claim_extractor.generate_claims(
        db=db,
        use_gemini=req.use_gemini,
        clear_existing=req.clear_existing,
    )
    return result


@router.get("/stats", response_model=claim_schema.ClaimStatsSchema)
def get_claim_stats(db: Session = Depends(get_db)):
    total_claims = db.query(models.Claim).count()
    pending_claims = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.pending)
        .count()
    )
    approved_claims = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.approved)
        .count()
    )
    rejected_claims = (
        db.query(models.Claim)
        .filter(models.Claim.status == models.ClaimStatus.rejected)
        .count()
    )
    total_conflicts = db.query(models.ConflictFlag).count()
    unresolved_conflicts = (
        db.query(models.ConflictFlag)
        .filter(models.ConflictFlag.resolved == False)  # noqa: E712
        .count()
    )
    insufficient_evidence_count = (
        db.query(models.Claim)
        .filter(models.Claim.insufficient_evidence == True)  # noqa: E712
        .count()
    )

    return {
        "total_claims": total_claims,
        "pending_claims": pending_claims,
        "approved_claims": approved_claims,
        "rejected_claims": rejected_claims,
        "total_conflicts": total_conflicts,
        "unresolved_conflicts": unresolved_conflicts,
        "insufficient_evidence_count": insufficient_evidence_count,
    }


@router.get("/conflicts", response_model=List[claim_schema.ConflictDetailSchema])
def list_conflicts(db: Session = Depends(get_db)):
    flags = (
        db.query(models.ConflictFlag)
        .options(
            joinedload(models.ConflictFlag.claim_a),
            joinedload(models.ConflictFlag.claim_b),
        )
        .order_by(models.ConflictFlag.created_at.desc())
        .all()
    )

    result = []
    for f in flags:
        claim_a_brief = None
        if f.claim_a:
            claim_a_brief = {
                "id": f.claim_a.id,
                "claim_text": f.claim_a.claim_text,
                "claim_type": f.claim_a.claim_type.value if hasattr(f.claim_a.claim_type, "value") else str(f.claim_a.claim_type),
                "status": f.claim_a.status.value if hasattr(f.claim_a.status, "value") else str(f.claim_a.status),
                "source_filename": f.claim_a.source_filename,
            }
        claim_b_brief = None
        if f.claim_b:
            claim_b_brief = {
                "id": f.claim_b.id,
                "claim_text": f.claim_b.claim_text,
                "claim_type": f.claim_b.claim_type.value if hasattr(f.claim_b.claim_type, "value") else str(f.claim_b.claim_type),
                "status": f.claim_b.status.value if hasattr(f.claim_b.status, "value") else str(f.claim_b.status),
                "source_filename": f.claim_b.source_filename,
            }
        result.append(
            {
                "id": f.id,
                "claim_a_id": f.claim_a_id,
                "claim_b_id": f.claim_b_id,
                "conflict_type": f.conflict_type,
                "description": f.description,
                "resolved": f.resolved,
                "created_at": f.created_at,
                "claim_a": claim_a_brief,
                "claim_b": claim_b_brief,
            }
        )
    return result


@router.get("", response_model=List[claim_schema.ClaimSchema])
def list_claims(
    status: Optional[str] = Query(default=None),
    claim_type: Optional[str] = Query(default=None),
    file_id: Optional[int] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.Claim).options(
        joinedload(models.Claim.citations),
        joinedload(models.Claim.review_history),
    )

    if status:
        try:
            status_enum = models.ClaimStatus(status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")
        query = query.filter(models.Claim.status == status_enum)

    if claim_type:
        try:
            type_enum = models.ClaimType(claim_type)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid claim_type: {claim_type}")
        query = query.filter(models.Claim.claim_type == type_enum)

    if file_id is not None:
        query = query.filter(models.Claim.source_file_id == file_id)

    claims = query.order_by(models.Claim.created_at.desc(), models.Claim.id.desc()).all()
    return [_serialize_claim(c, db) for c in claims]


@router.get("/{claim_id}", response_model=claim_schema.ClaimSchema)
def get_claim(claim_id: int, db: Session = Depends(get_db)):
    claim = (
        db.query(models.Claim)
        .options(
            joinedload(models.Claim.citations),
            joinedload(models.Claim.review_history),
        )
        .filter(models.Claim.id == claim_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")
    return _serialize_claim(claim, db)


@router.patch("/{claim_id}", response_model=claim_schema.ClaimSchema)
def update_claim(
    claim_id: int,
    payload: claim_schema.ClaimUpdateRequest,
    db: Session = Depends(get_db),
):
    claim = (
        db.query(models.Claim)
        .options(
            joinedload(models.Claim.citations),
            joinedload(models.Claim.review_history),
        )
        .filter(models.Claim.id == claim_id)
        .first()
    )
    if not claim:
        raise HTTPException(status_code=404, detail="Claim not found")

    prev_text = claim.claim_text
    prev_status = claim.status.value if hasattr(claim.status, "value") else str(claim.status)

    action_parts = []

    if payload.claim_text is not None:
        cleaned_text = payload.claim_text.strip()
        if not cleaned_text:
            raise HTTPException(status_code=400, detail="claim_text cannot be empty")
        if cleaned_text != claim.claim_text:
            claim.claim_text = cleaned_text
            action_parts.append("edited")

    if payload.status is not None:
        try:
            new_status_enum = models.ClaimStatus(payload.status)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {payload.status}")
        if new_status_enum != claim.status:
            claim.status = new_status_enum
            action_parts.append(new_status_enum.value)

    if not action_parts and not payload.comment:
        raise HTTPException(status_code=400, detail="No changes provided")

    action_label = "+".join(action_parts) if action_parts else "commented"
    new_status_str = claim.status.value if hasattr(claim.status, "value") else str(claim.status)

    history = models.ReviewHistory(
        claim_id=claim.id,
        action=action_label,
        previous_text=prev_text,
        new_text=claim.claim_text,
        previous_status=prev_status,
        new_status=new_status_str,
        comment=payload.comment.strip() if payload.comment else None,
    )
    db.add(history)
    db.commit()
    db.refresh(claim)

    return _serialize_claim(claim, db)
