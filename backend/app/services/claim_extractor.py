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


EXTENDED_STOPWORDS: Set[str] = STOPWORDS | {
    "git", "commit", "author", "date", "time", "timestamp", "files", "changed", "line",
    "page", "chat", "task", "row", "speaker", "id", "status", "message", "excerpt",
    "path", "json", "csv", "txt", "pdf", "docx", "example", "com", "org", "http", "https",
    "url", "code", "app", "backend", "frontend", "py", "js", "ts", "staging",
    "production", "prod", "dev", "local", "release", "repo", "branch",
    "rule", "rules", "strictly", "constrained", "producing", "lacks", "applying", "generic",
    "dangerous", "introduces", "invents", "facts", "leaks", "confidential", "credentials",
    "boundaries", "discrepancies", "discrepancy", "isolated", "prominent", "warning",
    "uncertainty", "matrix", "conflict", "conflicts", "state", "states", "notes", "personal",
    "item", "items", "step", "steps", "details", "summary", "assignee", "priority", "due",
    "before", "after", "between", "sources", "source", "material", "reference", "link",
    "statement", "statements", "indicates", "different", "when", "slack", "github",
    "standard", "rag", "models", "generate", "ambiguous", "synthesis", "invent", "false",
    "most", "challenging", "technical", "problem", "resolution", "prevention", "feat",
    "fix", "chore", "add", "added", "update", "updated", "create", "created", "initial",
    "overview", "handover",
}


def _clean_subject_text(text: str) -> str:
    s = re.sub(r"\((?:e\.g\.?|for example)[^)]*\)", "", text, flags=re.IGNORECASE)
    s = re.sub(r"^Git Commit [0-9a-fA-F]+\s*(?:by [^:]+ on [^:]+)?:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\[Changed files:.*?\]", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^Chat \([^)]+\):\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^Task [A-Za-z0-9_-]+\s*\[[^\]]+\]:\s*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(Assignee:.*?Due:.*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"\(Assignee:.*?\)", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^(?:feat|fix|chore|docs|refactor|todo|fixme|action item)[:\s-]*", "", s, flags=re.IGNORECASE)
    s = re.sub(r"^\d+\.\s*", "", s)
    return s.strip()


def _subject_tokens(text: str) -> Set[str]:
    clean = _clean_subject_text(text)
    words = re.findall(r"[a-zA-Z0-9_-]{3,}", clean.lower())
    return {w for w in words if w not in EXTENDED_STOPWORDS}


def _extract_task_id(text: str, record_id: Optional[str] = None) -> Optional[str]:
    if record_id and re.match(r"^(?:TASK|ISSUE|BUG|FEAT|T)[-_]?\d+$", record_id, re.IGNORECASE):
        return record_id.upper()
    m = re.search(r"\b(TASK-\d+|ISSUE-\d+|BUG-\d+|FEAT-\d+)\b", text, re.IGNORECASE)
    if m:
        return m.group(1).upper()
    m2 = re.search(r"\b(?:Task|Issue|Bug)\s*#?(\d+)\b", text, re.IGNORECASE)
    if m2:
        return f"TASK-{m2.group(1)}"
    return None


def _extract_git_hash(text: str, record_id: Optional[str] = None) -> Optional[str]:
    if record_id and re.match(r"^[0-9a-fA-F]{6,40}$", record_id):
        return record_id.lower()
    m = re.search(r"\bGit Commit ([0-9a-fA-F]{6,40})\b", text, re.IGNORECASE)
    if m:
        return m.group(1).lower()
    return None


def _extract_status_sentiment(text: str, claim_type: models.ClaimType) -> str:
    clean = _clean_subject_text(text).lower()
    raw = text.lower()
    # Completed indicators
    if (
        re.search(
            r"\b(completed|finished|shipped|deployed|resolved|verified in staging|implemented|working|merged|passed|done)\b",
            clean,
        )
        or re.search(r"\[(?:done|completed|closed|resolved|merged)\]", raw)
    ):
        if not re.search(r"\b(not yet|pending|still pending|unimplemented|todo|fixme|open|blocked)\b", clean):
            return "completed"

    # Pending / in-progress / blocked indicators
    if (
        re.search(
            r"\b(pending|still pending|in progress|not yet|open|wip|todo|fixme|blocked|blocker|needs to be|incomplete)\b",
            clean,
        )
        or re.search(r"\[(?:open|pending|in[ -_]?progress|todo|backlog)\]", raw)
    ):
        return "pending"

    if claim_type == models.ClaimType.completed_feature:
        return "completed"
    if claim_type in (
        models.ClaimType.pending_feature,
        models.ClaimType.todo_fixme,
        models.ClaimType.blocker_risk,
    ):
        return "pending"
    return "neutral"


def _is_problem_solution_pair(text_a: str, text_b: str) -> bool:
    problem_words = {
        "hallucination", "hallucinations", "leak", "leaks", "vulnerability", "risk", "risks",
        "threat", "danger", "dangerous", "unverified", "discrepancy", "discrepancies", "invent", "invents",
    }
    solution_words = {
        "rule", "rules", "mitigate", "mitigates", "safeguard", "safeguards", "prevent", "prevents",
        "prevention", "strictly", "constrained", "enforce", "enforcement", "assertion", "grounding",
        "traceability", "isolates", "isolated",
    }
    toks_a = set(re.findall(r"[a-z]+", text_a.lower()))
    toks_b = set(re.findall(r"[a-z]+", text_b.lower()))
    is_a_prob = bool(toks_a & problem_words)
    is_b_prob = bool(toks_b & problem_words)
    is_a_sol = bool(toks_a & solution_words)
    is_b_sol = bool(toks_b & solution_words)
    return (is_a_prob and is_b_sol) or (is_b_prob and is_a_sol)


def _detect_conflicts(db: Session) -> int:
    """
    Detect potential contradictions, review warnings, and insufficient evidence flags across stored claims.
    Re-evaluates unresolved flags to eliminate false positives while preserving human-resolved flags.
    """
    claims = db.query(models.Claim).all()
    resolved_flags = (
        db.query(models.ConflictFlag)
        .filter(models.ConflictFlag.resolved == True)  # noqa: E712
        .all()
    )
    existing_pairs: Set[Tuple[int, Optional[int], str]] = set()
    for flag in resolved_flags:
        if flag.claim_b_id is not None:
            existing_pairs.add(
                (min(flag.claim_a_id, flag.claim_b_id), max(flag.claim_a_id, flag.claim_b_id), flag.conflict_type)
            )
        else:
            existing_pairs.add((flag.claim_a_id, None, flag.conflict_type))

    # Clear unresolved flags so fresh, accurate analysis replaces obsolete false-positives
    db.query(models.ConflictFlag).filter(models.ConflictFlag.resolved == False).delete()  # noqa: E712

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
                        resolved=False,
                    )
                )
                existing_pairs.add(key)
                new_flags += 1

    # Pre-extract metadata for all claims
    claim_meta: Dict[int, dict] = {}
    for c in claims:
        first_cit = c.citations[0] if c.citations else None
        chunk = first_cit.evidence_chunk if first_cit else None
        rec_id = getattr(chunk, "record_id", None) if chunk else None
        tid = _extract_task_id(c.claim_text, rec_id)
        ghash = _extract_git_hash(c.claim_text, rec_id)
        tokens = _subject_tokens(c.claim_text)
        sentiment = _extract_status_sentiment(c.claim_text, c.claim_type)
        claim_meta[c.id] = {
            "task_id": tid,
            "git_hash": ghash,
            "tokens": tokens,
            "sentiment": sentiment,
            "source_type": getattr(chunk, "source_type", "document") if chunk else "document",
        }

    # 2. Pairwise contradiction / review warning analysis
    n = len(claims)
    for i in range(n):
        for j in range(i + 1, n):
            c_a = claims[i]
            c_b = claims[j]
            meta_a = claim_meta[c_a.id]
            meta_b = claim_meta[c_b.id]

            # Rule A: Different task IDs MUST NOT be flagged as contradictions
            tid_a = meta_a["task_id"]
            tid_b = meta_b["task_id"]
            if tid_a and tid_b:
                if tid_a != tid_b:
                    continue  # Different tasks naturally have independent statuses
                # Same task ID: check for status contradiction
                st_a = meta_a["sentiment"]
                st_b = meta_b["sentiment"]
                if (st_a == "completed" and st_b == "pending") or (st_a == "pending" and st_b == "completed"):
                    pair = (min(c_a.id, c_b.id), max(c_a.id, c_b.id), "contradiction")
                    if pair not in existing_pairs:
                        db.add(
                            models.ConflictFlag(
                                claim_a_id=c_a.id,
                                claim_b_id=c_b.id,
                                conflict_type="contradiction",
                                description=(
                                    f"Direct status contradiction on task {tid_a}: "
                                    f"'{c_a.source_filename}' reports {st_a} while "
                                    f"'{c_b.source_filename}' reports {st_b}."
                                ),
                                resolved=False,
                            )
                        )
                        existing_pairs.add(pair)
                        new_flags += 1
                # If statuses match or are compatible, it's agreement (no conflict)
                continue

            # Rule B: Different Git commits are distinct changesets unless referencing the same task
            ghash_a = meta_a["git_hash"]
            ghash_b = meta_b["git_hash"]
            if ghash_a and ghash_b:
                if ghash_a != ghash_b:
                    continue  # Distinct commits; unrelated TODOs/commits do not conflict

            # Rule C: Problem statement vs Solution safeguard
            if _is_problem_solution_pair(c_a.claim_text, c_b.claim_text):
                continue

            # Rule D: Corroborating statements from the same file (e.g. Uncertainty Matrix architecture)
            if c_a.source_file_id == c_b.source_file_id:
                raw_a = c_a.claim_text.lower()
                raw_b = c_b.claim_text.lower()
                if "uncertainty" in raw_a and "uncertainty" in raw_b:
                    continue

            # Rule E: Topic overlap and status compatibility check
            toks_a = meta_a["tokens"]
            toks_b = meta_b["tokens"]
            overlap = toks_a & toks_b
            if not overlap:
                continue

            st_a = meta_a["sentiment"]
            st_b = meta_b["sentiment"]

            # Agreement: Two sources reporting the same pending status do NOT conflict
            if (st_a == "pending" and st_b == "pending") or (st_a == "completed" and st_b == "completed"):
                continue

            # Check for genuine status incompatibility (one completed, one pending/blocked)
            if (st_a == "completed" and st_b == "pending") or (st_a == "pending" and st_b == "completed"):
                union_len = len(toks_a | toks_b)
                jaccard = len(overlap) / union_len if union_len > 0 else 0.0

                if len(overlap) >= 2 and jaccard >= 0.25:
                    shared_str = ", ".join(sorted(overlap)[:5])
                    # High confidence: confirmed contradiction
                    if (len(overlap) >= 3 and jaccard >= 0.35) or (len(overlap) >= 2 and jaccard >= 0.4):
                        c_type = "contradiction"
                        desc = (
                            f"Potential status contradiction on topic ({shared_str}): "
                            f"'{c_a.source_filename}' indicates completion while "
                            f"'{c_b.source_filename}' indicates pending/blocked work."
                        )
                    else:
                        # Moderate ambiguity: flag as a review warning rather than declaring a confirmed contradiction
                        c_type = "review_warning"
                        desc = (
                            f"Review warning: Potential status divergence on topic ({shared_str}): "
                            f"'{c_a.source_filename}' indicates {st_a} while "
                            f"'{c_b.source_filename}' indicates {st_b}. Human review recommended."
                        )

                    pair = (min(c_a.id, c_b.id), max(c_a.id, c_b.id), c_type)
                    if pair not in existing_pairs:
                        db.add(
                            models.ConflictFlag(
                                claim_a_id=c_a.id,
                                claim_b_id=c_b.id,
                                conflict_type=c_type,
                                description=desc,
                                resolved=False,
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
