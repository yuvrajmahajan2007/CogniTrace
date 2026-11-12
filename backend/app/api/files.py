import os
import shutil
from typing import List
from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from ..db import SessionLocal
from .. import models
from ..core import config
from ..services import parser
from ..schemas import file as file_schema

router = APIRouter()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def _sanitize_filename(raw_name: str) -> str:
    """Strip any directory components (POSIX or Windows) and reject unsafe names."""
    normalized = (raw_name or "").replace("\\", "/")
    safe_name = os.path.basename(normalized).strip()
    if not safe_name or safe_name in {".", ".."}:
        raise HTTPException(status_code=400, detail="Invalid filename")
    return safe_name


def _safe_upload_path(filename: str) -> str:
    """Resolve a path inside UPLOAD_DIR and guarantee it cannot escape via traversal."""
    upload_root = os.path.abspath(config.settings.UPLOAD_DIR)
    os.makedirs(upload_root, exist_ok=True)
    candidate = os.path.abspath(os.path.join(upload_root, filename))
    if os.path.commonpath([upload_root, candidate]) != upload_root:
        raise HTTPException(status_code=400, detail="Invalid file path")
    return candidate


@router.post("/upload", response_model=file_schema.UploadResponse)
async def upload_files(files: List[UploadFile] = File(...), background_tasks: BackgroundTasks = None, db: Session = Depends(get_db)):
    allowed = set(config.settings.ALLOWED_TYPES.split(","))
    max_bytes = config.settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    uploaded = []
    for upload in files:
        safe_filename = _sanitize_filename(upload.filename)
        if "." not in safe_filename:
            raise HTTPException(status_code=400, detail="File must have an extension")
        ext = safe_filename.rsplit(".", 1)[-1].lower()
        if ext not in allowed:
            raise HTTPException(status_code=400, detail=f"Unsupported file type: {ext}")
        # read size
        contents = await upload.read()
        if len(contents) > max_bytes:
            raise HTTPException(status_code=400, detail="File exceeds maximum size of 20 MB")
        # store file safely inside UPLOAD_DIR
        file_path = _safe_upload_path(safe_filename)
        counter = 1
        base, _ = os.path.splitext(safe_filename)
        while os.path.exists(file_path):
            file_path = _safe_upload_path(f"{base}_{counter}.{ext}")
            counter += 1
        with open(file_path, "wb") as f:
            f.write(contents)
        # DB record
        db_file = models.UploadedFile(
            filename=safe_filename,
            content_type=upload.content_type or "application/octet-stream",
            size_bytes=len(contents),
            status=models.ParsingStatus.pending,
        )
        db.add(db_file)
        db.commit()
        db.refresh(db_file)
        # schedule parsing
        background_tasks.add_task(parser.parse_file, db_file.id, file_path)
        uploaded.append({"id": db_file.id, "filename": db_file.filename, "status": db_file.status.value})
    return {"uploaded": uploaded}

@router.get("", response_model=List[file_schema.FileMeta])
def list_files(db: Session = Depends(get_db)):
    files = db.query(models.UploadedFile).all()
    return [file_schema.FileMeta.model_validate(f) for f in files]

@router.get("/{file_id}", response_model=file_schema.FileDetail)
def get_file(file_id: int, db: Session = Depends(get_db)):
    f = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    return file_schema.FileDetail.model_validate(f)

@router.get("/{file_id}/content", response_model=List[file_schema.EvidenceChunkSchema])
def get_content(file_id: int, db: Session = Depends(get_db)):
    f = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    chunks = db.query(models.EvidenceChunk).filter(models.EvidenceChunk.file_id == file_id).order_by(models.EvidenceChunk.chunk_index).all()
    return [file_schema.EvidenceChunkSchema.model_validate(c) for c in chunks]

@router.delete("/{file_id}", response_model=file_schema.DeleteResponse)
def delete_file(file_id: int, db: Session = Depends(get_db)):
    f = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    if not f:
        raise HTTPException(status_code=404, detail="File not found")
    # delete any conflict flags referencing claims from this file
    claim_ids = [c.id for c in db.query(models.Claim.id).filter(models.Claim.source_file_id == file_id).all()]
    if claim_ids:
        db.query(models.ConflictFlag).filter(
            (models.ConflictFlag.claim_a_id.in_(claim_ids))
            | (models.ConflictFlag.claim_b_id.in_(claim_ids))
        ).delete(synchronize_session=False)
    # delete physical file safely inside UPLOAD_DIR
    try:
        safe_name = _sanitize_filename(f.filename)
        os.remove(_safe_upload_path(safe_name))
    except (FileNotFoundError, HTTPException):
        pass
    db.delete(f)
    db.commit()
    return {"deleted": True, "id": file_id}
