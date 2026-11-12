import re
from typing import Dict, List, Optional, Set, Tuple
from sqlalchemy.orm import Session
from .. import models

# Ordered by specificity so the most actionable category wins when multiple match
CATEGORY_RULES: List[Tuple[models.ClaimType, re.Pattern]] = [
    (
        models.ClaimType.todo_fixme,
        re.compile(r"\b(TODO|FIXME|HACK|XXX|ACTION ITEM)\b[:\s-]*", re.IGNORECASE),
    ),
    (
        models.ClaimType.blocker_risk,
        re.compile(
            r"\b(blocker|blocked\s+by|blocking|risk|critical\s+issue|bottleneck|incident|outage|vulnerability|cannot\s+proceed|stuck\s+on|showstopper)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.architecture_decision,
        re.compile(
            r"\b(architecture|architectural|design\s+decision|decided\s+to\s+use|we\s+chose|schema|monolith|microservice|event[- ]driven|rest\s+api|graphql|sqlite|postgresql|postgres|mysql|redis|orm)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.project_decision,
        re.compile(
            r"\b(decision|decided|agreed\s+to|approved|confirmed|adopted|standardized\s+on|will\s+use|migrating\s+to|switched\s+to|selected)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.pending_feature,
        re.compile(
            r"(\[(open|pending|in[\s_-]?progress|todo|backlog)\])|\b(pending|incomplete|in\s+progress|not\s+yet|remaining|upcoming|planned|wip|missing|unimplemented|needs?\s+to\s+be|deferred|outstanding)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.completed_feature,
        re.compile(
            r"(\[(done|completed|closed|resolved|merged)\])|\b(completed|implemented|finished|shipped|deployed|released|working|verified|passed|resolved|done|built|functional|feat:|fix:)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.dependency,
        re.compile(
            r"\b(depends\s+on|dependency|dependencies|requires|prerequisite|waiting\s+on|upstream|downstream|integrated\s+with|relies\s+on|third[- ]party)\b",
            re.IGNORECASE,
        ),
    ),
    (
        models.ClaimType.technology,
        re.compile(
            r"\b(react|vite|tailwind|fastapi|python|sqlalchemy|pymupdf|python-docx|pydantic|typescript|node\.?js|docker|kubernetes|aws|gcp|azure|jwt|oauth|gemini|uvicorn|httpx)\b",
            re.IGNORECASE,
        ),
    ),
]

INSUFFICIENT_EVIDENCE_PATTERN = re.compile(
    r"\b(tbd|tba|to\s+be\s+decided|to\s+be\s+determined|unclear|unknown|maybe|possibly|\?\?\?)\b",
    re.IGNORECASE,
)

STOPWORDS: Set[str] = {
    "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for", "of", "with",
    "by", "from", "is", "are", "was", "were", "be", "been", "being", "have", "has", "had",
    "do", "does", "did", "will", "would", "could", "should", "may", "might", "must",
    "this", "that", "these", "those", "it", "its", "we", "our", "they", "their", "as",
    "not", "no", "yes", "yet", "still", "already", "now", "all", "any", "each", "also",
    "feature", "features", "module", "system", "project", "support", "using", "use",
    "completed", "implemented", "finished", "working", "verified", "done", "built",
    "pending", "incomplete", "progress", "remaining", "planned", "missing", "needs",
    "todo", "fixme", "blocker", "risk", "decision", "decided", "dependency", "requires",
}

COMPETING_TECH_GROUPS: List[Tuple[str, Set[str]]] = [
    ("database", {"sqlite", "postgresql", "postgres", "mysql", "mongodb"}),
    ("api_style", {"rest", "graphql", "grpc"}),
    ("frontend_framework", {"react", "vue", "angular", "svelte"}),
]


def _is_heading_or_boilerplate(text: str) -> bool:
    s = text.strip()
    if re.match(r"^Page\s+\d+\s+of\s+\d+$", s, re.IGNORECASE):
        return True
    # Numbered or ALL-CAPS short headings without verb/punctuation
    if len(s) < 70 and re.match(r"^(\d+\.\s+)?[A-Z0-9\s&/:-]+$", s) and not s.endswith("."):
        return True
    return False


def _reconstruct_paragraphs_from_chunks(chunks: List[models.EvidenceChunk]) -> List[Tuple[str, models.EvidenceChunk]]:
    """
    Rejoin wrapped PDF lines into complete statements/sentences while preserving
    the EvidenceChunk where each statement originates.
    """
    combined_lines: List[Tuple[str, models.EvidenceChunk]] = []
    for chunk in chunks:
        for raw_line in re.split(r"\r?\n+", chunk.text):
            cleaned = re.sub(r"^\s*[-*•]+\s+", "", raw_line).strip()
            if cleaned:
                combined_lines.append((cleaned, chunk))

    paragraphs: List[Tuple[str, models.EvidenceChunk]] = []
    buf_text = ""
    buf_chunk: Optional[models.EvidenceChunk] = None

    # Pattern for a new labeled bullet/heading line like "Frontend: ..." or "6. TECHNICAL..."
    new_item_pattern = re.compile(r"^([A-Z][A-Za-z0-9\s&/-]{2,35}:\s|\d+\.\s+[A-Z])")

    for line, chunk in combined_lines:
        if not buf_text:
            buf_text = line
            buf_chunk = chunk
            continue

        # Flush if previous buffer ended a sentence or current line starts a new labeled item
        if buf_text.endswith((".", "!", "?")) or new_item_pattern.match(line):
            paragraphs.append((buf_text, buf_chunk))
            buf_text = line
            buf_chunk = chunk
        else:
            # Join wrapped line cleanly
            if buf_text.endswith("-"):
                buf_text = buf_text[:-1] + line
            else:
                buf_text = buf_text + " " + line

    if buf_text and buf_chunk is not None:
        paragraphs.append((buf_text, buf_chunk))

    segments: List[Tuple[str, models.EvidenceChunk]] = []
    for para, p_chunk in paragraphs:
        if _is_heading_or_boilerplate(para):
            continue
        if len(para) > 260:
            for sent in re.split(r"(?<=[.!?])\s+", para):
                s_clean = sent.strip()
                if 18 <= len(s_clean) <= 500 and not _is_heading_or_boilerplate(s_clean):
                    segments.append((s_clean, p_chunk))
        elif 18 <= len(para) <= 500:
            segments.append((para, p_chunk))
    return segments


def _classify_segment(segment: str) -> Optional[models.ClaimType]:
    for claim_type, pattern in CATEGORY_RULES:
        if pattern.search(segment):
            return claim_type
    return None


def _is_insufficient_evidence(segment: str) -> bool:
    s = segment.strip()
    if len(s) < 25:
        return True
    if s[0].islower() or s.endswith((",", ";", ":", "-")):
        return True
    if INSUFFICIENT_EVIDENCE_PATTERN.search(s):
        return True
    return False


def _topic_tokens(text: str) -> Set[str]:
    words = re.findall(r"[a-zA-Z0-9_-]{3,}", text.lower())
    return {w for w in words if w not in STOPWORDS}


def _detect_conflicts(db: Session) -> int:
    """Detect potential contradictions and insufficient evidence flags across stored claims."""
    claims = db.query(models.Claim).all()
    existing_flags = db.query(models.ConflictFlag).all()

    existing_pairs: Set[Tuple[int, Optional[int], str]] = set()
    for flag in existing_flags:
        if flag.claim_b_id is not None:
            pair = (min(flag.claim_a_id, flag.claim_b_id), max(flag.claim_a_id, flag.claim_b_id), flag.conflict_type)
        else:
            pair = (flag.claim_a_id, None, flag.conflict_type)
        existing_pairs.add(pair)

    new_flags = 0

    # 1. Flag insufficient evidence claims
    for claim in claims:
        if claim.insufficient_evidence:
            key = (claim.id, None, "insufficient_evidence")
            if key not in existing_pairs:
                db.add(
                    models.ConflictFlag(
                        claim_a_id=claim.id,
                        claim_b_id=None,
                        conflict_type="insufficient_evidence",
                        description=(
                            f"Claim from '{claim.source_filename}' has brief or ambiguous wording "
                            f"and requires human verification of supporting context."
                        ),
                    )
                )
                existing_pairs.add(key)
                new_flags += 1

    # 2. Completed vs Pending/Blocker contradictions on overlapping topics
    completed_claims = [c for c in claims if c.claim_type == models.ClaimType.completed_feature]
    pending_or_blocked = [
        c
        for c in claims
        if c.claim_type in (models.ClaimType.pending_feature, models.ClaimType.blocker_risk, models.ClaimType.todo_fixme)
    ]

    for comp in completed_claims:
        comp_tokens = _topic_tokens(comp.claim_text)
        if not comp_tokens:
            continue
        for pend in pending_or_blocked:
            if comp.id == pend.id:
                continue
            pend_tokens = _topic_tokens(pend.claim_text)
            overlap = comp_tokens & pend_tokens
            if len(overlap) >= 2:
                pair = (min(comp.id, pend.id), max(comp.id, pend.id), "contradiction")
                if pair not in existing_pairs:
                    shared_str = ", ".join(sorted(overlap)[:5])
                    db.add(
                        models.ConflictFlag(
                            claim_a_id=comp.id,
                            claim_b_id=pend.id,
                            conflict_type="contradiction",
                            description=(
                                f"Potential status contradiction on topic ({shared_str}): "
                                f"'{comp.source_filename}' indicates completion while "
                                f"'{pend.source_filename}' indicates pending/blocked work."
                            ),
                        )
                    )
                    existing_pairs.add(pair)
                    new_flags += 1

    # 3. Competing technology / architecture choices
    tech_claims = [
        c
        for c in claims
        if c.claim_type in (models.ClaimType.architecture_decision, models.ClaimType.technology, models.ClaimType.project_decision)
    ]
    for group_name, group_terms in COMPETING_TECH_GROUPS:
        matched_by_term: Dict[str, List[models.Claim]] = {}
        for claim in tech_claims:
            tokens = set(re.findall(r"[a-z0-9]+", claim.claim_text.lower()))
            for term in group_terms:
                if term in tokens:
                    matched_by_term.setdefault(term, []).append(claim)
        if len(matched_by_term) >= 2:
            terms_sorted = sorted(matched_by_term.keys())
            first_term = terms_sorted[0]
            for other_term in terms_sorted[1:]:
                c_a = matched_by_term[first_term][0]
                c_b = matched_by_term[other_term][0]
                if c_a.id == c_b.id:
                    continue
                pair = (min(c_a.id, c_b.id), max(c_a.id, c_b.id), "contradiction")
                if pair not in existing_pairs:
                    db.add(
                        models.ConflictFlag(
                            claim_a_id=c_a.id,
                            claim_b_id=c_b.id,
                            conflict_type="contradiction",
                            description=(
                                f"Potential {group_name} conflict: '{c_a.source_filename}' references "
                                f"'{first_term}' while '{c_b.source_filename}' references '{other_term}'."
                            ),
                        )
                    )
                    existing_pairs.add(pair)
                    new_flags += 1

    db.commit()
    return new_flags


def generate_claims(db: Session, use_gemini: bool = False, clear_existing: bool = False) -> dict:
    """
    Generate candidate claims strictly grounded in stored EvidenceChunk rows.
    Gemini AI extraction is optional and disabled by default; deterministic rule-based
    extraction always runs as the primary / fallback extractor.
    """
    if clear_existing:
        db.query(models.ConflictFlag).delete()
        db.query(models.ReviewHistory).delete()
        db.query(models.Citation).delete()
        db.query(models.Claim).delete()
        db.commit()

    completed_files = (
        db.query(models.UploadedFile)
        .filter(models.UploadedFile.status == models.ParsingStatus.completed)
        .all()
    )
    file_map = {f.id: f for f in completed_files}

    if not file_map:
        return {
            "generated_count": 0,
            "skipped_duplicates": 0,
            "conflicts_detected": 0,
            "insufficient_evidence_flagged": 0,
            "extraction_method": "rule_based",
            "message": "No parsed documents available. Upload and parse documents first.",
        }

    chunks = (
        db.query(models.EvidenceChunk)
        .filter(models.EvidenceChunk.file_id.in_(list(file_map.keys())))
        .order_by(models.EvidenceChunk.file_id, models.EvidenceChunk.chunk_index)
        .all()
    )

    if not chunks:
        return {
            "generated_count": 0,
            "skipped_duplicates": 0,
            "conflicts_detected": 0,
            "insufficient_evidence_flagged": 0,
            "extraction_method": "rule_based",
            "message": "No extracted evidence chunks found in parsed documents.",
        }

    existing_claims = db.query(models.Claim).all()
    seen_keys: Set[Tuple[str, int]] = {
        (c.claim_text.strip().lower(), c.source_file_id) for c in existing_claims
    }

    generated_count = 0
    skipped_duplicates = 0
    insufficient_count = 0

    # Group chunks by file so wrapped lines across adjacent chunks on the same page can be rejoined
    chunks_by_file: Dict[int, List[models.EvidenceChunk]] = {}
    for ch in chunks:
        chunks_by_file.setdefault(ch.file_id, []).append(ch)

    for file_id, file_chunks in chunks_by_file.items():
        source_file = file_map.get(file_id)
        if not source_file:
            continue

        # Structured records (git, chat, task) are already 1 record per chunk; never merge adjacent records
        if getattr(source_file, "source_type", "document") in ("git", "chat", "task"):
            segments = [(ch.text.strip(), ch) for ch in file_chunks if ch.text.strip()]
        else:
            segments = _reconstruct_paragraphs_from_chunks(file_chunks)
        for segment, chunk in segments:
            claim_type = _classify_segment(segment)
            if not claim_type:
                continue

            dedup_key = (segment.strip().lower(), source_file.id)
            if dedup_key in seen_keys:
                skipped_duplicates += 1
                continue
            seen_keys.add(dedup_key)

            insufficient = _is_insufficient_evidence(segment)
            if insufficient:
                insufficient_count += 1

            claim = models.Claim(
                claim_text=segment,
                claim_type=claim_type,
                status=models.ClaimStatus.pending,
                source_file_id=source_file.id,
                source_filename=source_file.filename,
                extraction_method="rule_based",
                insufficient_evidence=insufficient,
            )
            db.add(claim)
            db.flush()  # get claim.id before adding citation

            citation = models.Citation(
                claim_id=claim.id,
                evidence_chunk_id=chunk.id,
                filename=source_file.filename,
                page_number=chunk.page_number,
                line_number=chunk.line_number,
                json_path=chunk.json_path,
                excerpt=chunk.text[:1000],
            )
            db.add(citation)
            generated_count += 1

    db.commit()
    conflicts_detected = _detect_conflicts(db)

    method_note = "rule_based"
    msg = (
        f"Generated {generated_count} candidate claim(s) from {len(chunks)} evidence chunk(s). "
        f"Flagged {conflicts_detected} conflict/evidence issue(s)."
    )
    if use_gemini:
        msg += " (Gemini extraction not configured; deterministic rule-based extractor used.)"

    return {
        "generated_count": generated_count,
        "skipped_duplicates": skipped_duplicates,
        "conflicts_detected": conflicts_detected,
        "insufficient_evidence_flagged": insufficient_count,
        "extraction_method": method_note,
        "message": msg,
    }
