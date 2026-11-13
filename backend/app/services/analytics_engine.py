import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Set, Tuple
from sqlalchemy import func
from sqlalchemy.orm import Session
from .. import models


def _is_synthetic(filename: Optional[str], text: Optional[str] = None) -> bool:
    """
    Identify synthetic or mock demonstration records based on filename markers
    and explicit mock identity markers, avoiding loose word matching in document text.
    """
    fn = (filename or "").lower()
    if any(marker in fn for marker in ("synthetic_", "_synthetic", "sample_", "_sample", "test_sample", "mock_", "_mock")):
        return True
    if fn in (
        "synthetic_sprint_tasks.csv",
        "sample_task_records.csv",
        "sample_chat_export.json",
        "sample_git_activity.json",
        "synthetic_team_chat.txt",
        "test_sample.json",
        "bad_git.pdf",
        "bad.json",
    ):
        return True
    if text:
        if re.search(r"\b(?:mock user|dummy user|fake user)\b", text, re.IGNORECASE):
            return True
        if re.search(r"<(?:mock|dummy|fake|test)@example\.com>", text, re.IGNORECASE):
            return True
    return False


def _clean_author_name(author_str: Optional[str]) -> str:
    """Extract clean display name from author string (stripping email or metadata)."""
    if not author_str:
        return "Unknown"
    # Strips `<user@example.com>`
    clean = re.sub(r"<[^>]+>", "", author_str).strip()
    return clean or author_str.strip()


def _normalize_iso_date(date_str: Optional[str], fallback_dt: Optional[datetime] = None) -> str:
    """Normalize timestamp string into YYYY-MM-DD format for timeline and time series."""
    if date_str:
        # Match YYYY-MM-DD
        m = re.search(r"\b(\d{4}-\d{2}-\d{2})\b", date_str)
        if m:
            return m.group(1)
    if fallback_dt:
        return fallback_dt.strftime("%Y-%m-%d")
    return "Unknown"


# ============================================================================
# 1. Task Analytics
# ============================================================================

def get_task_analytics(db: Session, deduplicate: bool = True) -> Dict[str, Any]:
    """
    Retrieve task distribution by status, priority, and assignee.
    Uses actual imported EvidenceChunk rows where source_type == 'task'.
    When deduplicate=True (default), unique task records are analyzed rather than
    raw chunks, preventing double-counting across overlapping or repeated file imports.
    """
    chunks = (
        db.query(models.EvidenceChunk, models.UploadedFile.filename)
        .join(models.UploadedFile, models.EvidenceChunk.file_id == models.UploadedFile.id)
        .filter(models.EvidenceChunk.source_type == "task")
        .order_by(models.EvidenceChunk.id.asc())
        .all()
    )

    if not chunks:
        return {
            "total_tasks": 0,
            "total_chunks": 0,
            "unique_task_ids": 0,
            "duplicate_chunks_count": 0,
            "by_status": [],
            "by_priority": [],
            "by_assignee": [],
            "records": [],
            "all_chunk_records": [],
            "summary": "No task records found in the project database.",
        }

    all_chunk_records: List[Dict[str, Any]] = []
    canonical_tasks: Dict[str, Dict[str, Any]] = {}

    for ch, filename in chunks:
        m_id = re.search(r"Task\s+([A-Za-z0-9_-]+)", ch.text, re.IGNORECASE)
        task_id = ch.record_id or (m_id.group(1).upper() if m_id else f"TASK-{ch.id}")

        m_status = re.search(r"\[([^\]]+)\]:", ch.text)
        status_label = m_status.group(1).strip().capitalize() if m_status else "Unspecified"
        if status_label.lower() in ("done", "closed", "resolved"):
            status_label = "Completed"
        elif status_label.lower() in ("open", "todo", "backlog"):
            status_label = "Open"
        elif "progress" in status_label.lower():
            status_label = "In Progress"

        m_pri = re.search(r"Priority:\s*([^,\)]+)", ch.text, re.IGNORECASE)
        priority_label = m_pri.group(1).strip().capitalize() if m_pri else "Unspecified"

        assignee = _clean_author_name(ch.author)
        if assignee == "Unknown":
            m_assignee = re.search(r"Assignee:\s*([^,\)]+)", ch.text, re.IGNORECASE)
            if m_assignee:
                assignee = m_assignee.group(1).strip()

        m_due = re.search(r"Due:\s*([^,\)]+)", ch.text, re.IGNORECASE)
        due_date = ch.record_timestamp or (m_due.group(1).strip() if m_due else None)

        m_title = re.search(r"\]:\s*(.*?)(?:\s*-\s*|\s*\(Assignee:|$)", ch.text)
        title = m_title.group(1).strip() if m_title else ch.text[:80]

        is_synth = _is_synthetic(filename, ch.text)

        rec = {
            "task_id": task_id,
            "title": title,
            "status": status_label,
            "priority": priority_label,
            "assignee": assignee,
            "due_date": due_date,
            "is_synthetic": is_synth,
            "source_filename": filename,
            "chunk_id": ch.id,
            "file_id": ch.file_id,
        }
        all_chunk_records.append(rec)

        # Precedence-aware deduplication per task_id:
        # Genuine records take precedence over synthetic/test duplicates;
        # otherwise, the latest chunk_id reflects the most recent state.
        if deduplicate:
            if task_id in canonical_tasks:
                existing = canonical_tasks[task_id]
                if existing["is_synthetic"] and not is_synth:
                    canonical_tasks[task_id] = rec
                elif existing["is_synthetic"] == is_synth and ch.id > existing["chunk_id"]:
                    canonical_tasks[task_id] = rec
            else:
                canonical_tasks[task_id] = rec

    target_records = list(canonical_tasks.values()) if deduplicate else all_chunk_records

    status_counts: Dict[str, int] = {}
    priority_counts: Dict[str, int] = {}
    assignee_counts: Dict[str, int] = {}

    for r in target_records:
        st = r["status"]
        pr = r["priority"]
        asgn = r["assignee"]
        status_counts[st] = status_counts.get(st, 0) + 1
        priority_counts[pr] = priority_counts.get(pr, 0) + 1
        assignee_counts[asgn] = assignee_counts.get(asgn, 0) + 1

    by_status = [{"label": k, "count": v} for k, v in sorted(status_counts.items(), key=lambda x: -x[1])]
    by_priority = [{"label": k, "count": v} for k, v in sorted(priority_counts.items(), key=lambda x: -x[1])]
    by_assignee = [{"label": k, "count": v} for k, v in sorted(assignee_counts.items(), key=lambda x: -x[1])]

    completed_cnt = status_counts.get("Completed", 0)
    pending_cnt = sum(v for k, v in status_counts.items() if k != "Completed")
    dup_skipped = len(all_chunk_records) - len(target_records)

    priority_str = ", ".join(f"{item['label']} ({item['count']})" for item in by_priority[:3])
    summary = (
        f"Analyzed {len(target_records)} unique task(s) across {len(all_chunk_records)} evidence chunk(s)"
        f" ({dup_skipped} duplicate/superseded import chunk(s) reconciled)."
        f" {completed_cnt} completed, {pending_cnt} open/pending."
        f" Top priorities: {priority_str}."
    )

    return {
        "total_tasks": len(target_records),
        "total_chunks": len(all_chunk_records),
        "unique_task_ids": len(target_records),
        "duplicate_chunks_count": dup_skipped,
        "by_status": by_status,
        "by_priority": by_priority,
        "by_assignee": by_assignee,
        "records": target_records,
        "all_chunk_records": all_chunk_records,
        "summary": summary,
    }


# ============================================================================
# 2. Git Activity Analytics
# ============================================================================

def get_git_analytics(db: Session) -> Dict[str, Any]:
    """
    Retrieve Git commit activity over time, commits by author, and changed files frequency.
    """
    chunks = (
        db.query(models.EvidenceChunk, models.UploadedFile.filename)
        .join(models.UploadedFile, models.EvidenceChunk.file_id == models.UploadedFile.id)
        .filter(models.EvidenceChunk.source_type == "git")
        .order_by(models.EvidenceChunk.id)
        .all()
    )

    if not chunks:
        return {
            "total_commits": 0,
            "unique_commits": 0,
            "by_date": [],
            "by_author": [],
            "changed_files": [],
            "records": [],
            "summary": "No Git activity records found in the project database.",
        }

    date_counts: Dict[str, int] = {}
    author_counts: Dict[str, int] = {}
    file_frequencies: Dict[str, int] = {}
    seen_hashes: Set[str] = set()
    records: List[Dict[str, Any]] = []

    for ch, filename in chunks:
        commit_hash = ch.record_id or "unknown"
        clean_author = _clean_author_name(ch.author)
        date_iso = _normalize_iso_date(ch.record_timestamp)

        # Extract message and files
        m_msg = re.search(r":\s*(.*?)(?:\s*\[Changed files:|$)", ch.text)
        message = m_msg.group(1).strip() if m_msg else ch.text[:80]

        changed_list: List[str] = []
        m_files = re.search(r"\[Changed files:\s*(.*?)\]", ch.text)
        if m_files:
            raw_files = m_files.group(1).split(",")
            for rf in raw_files:
                cf = rf.strip()
                if cf:
                    changed_list.append(cf)
                    file_frequencies[cf] = file_frequencies.get(cf, 0) + 1

        seen_hashes.add(commit_hash[:12])
        date_counts[date_iso] = date_counts.get(date_iso, 0) + 1
        author_counts[clean_author] = author_counts.get(clean_author, 0) + 1

        records.append({
            "commit_hash": commit_hash,
            "author": clean_author,
            "date": date_iso,
            "timestamp": ch.record_timestamp,
            "message": message,
            "changed_files": changed_list,
            "is_synthetic": _is_synthetic(filename, ch.text),
            "source_filename": filename,
            "chunk_id": ch.id,
        })

    # Sort dates chronologically
    by_date = [{"date": k, "count": v} for k, v in sorted(date_counts.items(), key=lambda x: x[0])]
    by_author = [{"author": k, "count": v} for k, v in sorted(author_counts.items(), key=lambda x: -x[1])]
    changed_files = [
        {"file": k, "frequency": v}
        for k, v in sorted(file_frequencies.items(), key=lambda x: -x[1])[:15]
    ]

    summary = (
        f"Analyzed {len(records)} commit record(s) across {len(seen_hashes)} unique commit hash(es) "
        f"by {len(author_counts)} author(s). "
        f"{len(file_frequencies)} distinct file(s) modified."
    )

    return {
        "total_commits": len(records),
        "unique_commits": len(seen_hashes),
        "by_date": by_date,
        "by_author": by_author,
        "changed_files": changed_files,
        "records": records,
        "summary": summary,
    }


# ============================================================================
# 3. Claims Analytics
# ============================================================================

def get_claims_analytics(db: Session) -> Dict[str, Any]:
    """
    Retrieve claims distribution by approval/review status and category.
    """
    claims = db.query(models.Claim).all()

    if not claims:
        return {
            "total_claims": 0,
            "by_review_status": [],
            "by_category": [],
            "summary": "No extracted claims found in the project database.",
        }

    status_counts: Dict[str, int] = {}
    category_counts: Dict[str, int] = {}

    for c in claims:
        st = c.status.value if hasattr(c.status, "value") else str(c.status)
        status_counts[st] = status_counts.get(st, 0) + 1

        cat = c.claim_type.value if hasattr(c.claim_type, "value") else str(c.claim_type)
        category_counts[cat] = category_counts.get(cat, 0) + 1

    by_review_status = [
        {"status": k, "count": v} for k, v in sorted(status_counts.items(), key=lambda x: -x[1])
    ]
    by_category = [
        {"category": k, "count": v} for k, v in sorted(category_counts.items(), key=lambda x: -x[1])
    ]

    approved = status_counts.get("approved", 0)
    pending = status_counts.get("pending", 0)
    rejected = status_counts.get("rejected", 0)

    cat_str = ", ".join(f"{item['category']} ({item['count']})" for item in by_category[:3])
    summary = (
        f"Total claims: {len(claims)}. "
        f"{approved} approved, {pending} pending review, {rejected} rejected. "
        f"Top categories: {cat_str}."
    )

    return {
        "total_claims": len(claims),
        "by_review_status": by_review_status,
        "by_category": by_category,
        "summary": summary,
    }


# ============================================================================
# 4. Evidence Analytics
# ============================================================================

def get_evidence_analytics(db: Session) -> Dict[str, Any]:
    """
    Retrieve evidence chunk distribution by source type and source document.
    """
    chunks_query = (
        db.query(models.EvidenceChunk.source_type, func.count(models.EvidenceChunk.id))
        .group_by(models.EvidenceChunk.source_type)
        .all()
    )
    by_source_type = [{"source_type": st, "count": cnt} for st, cnt in sorted(chunks_query, key=lambda x: -x[1])]

    by_doc_query = (
        db.query(
            models.UploadedFile.id,
            models.UploadedFile.filename,
            models.UploadedFile.source_type,
            func.count(models.EvidenceChunk.id),
        )
        .join(models.EvidenceChunk, models.UploadedFile.id == models.EvidenceChunk.file_id)
        .group_by(models.UploadedFile.id, models.UploadedFile.filename, models.UploadedFile.source_type)
        .order_by(func.count(models.EvidenceChunk.id).desc())
        .all()
    )
    by_document = [
        {
            "file_id": fid,
            "filename": fn,
            "source_type": st,
            "chunk_count": cnt,
            "is_synthetic": _is_synthetic(fn),
        }
        for fid, fn, st, cnt in by_doc_query
    ]

    total_chunks = sum(item["count"] for item in by_source_type)

    src_str = ", ".join(f"{item['source_type']} ({item['count']})" for item in by_source_type)
    summary = (
        f"Total evidence chunks: {total_chunks} across {len(by_document)} source document(s). "
        f"Distribution by source: {src_str}."
    )

    return {
        "total_chunks": total_chunks,
        "by_source_type": by_source_type,
        "by_document": by_document,
        "summary": summary,
    }


# ============================================================================
# 5. Conflict Analytics
# ============================================================================

def get_conflict_analytics(db: Session) -> Dict[str, Any]:
    """
    Retrieve conflict and evidence warning statistics by type and source document.
    """
    flags = (
        db.query(models.ConflictFlag)
        .order_by(models.ConflictFlag.id)
        .all()
    )

    if not flags:
        return {
            "total_conflicts": 0,
            "unresolved_conflicts": 0,
            "resolved_conflicts": 0,
            "by_resolution_status": [
                {"status": "unresolved", "count": 0},
                {"status": "resolved", "count": 0},
            ],
            "by_conflict_type": [],
            "unresolved_by_type": [],
            "resolved_by_type": [],
            "by_document": [],
            "flags": [],
            "summary": "Zero unresolved conflicts or evidence warnings detected.",
        }

    type_counts: Dict[str, int] = {}
    doc_counts: Dict[str, int] = {}
    flag_details: List[Dict[str, Any]] = []

    for f in flags:
        c_type = f.conflict_type
        type_counts[c_type] = type_counts.get(c_type, 0) + 1

        docs: Set[str] = set()
        if f.claim_a and f.claim_a.source_filename:
            docs.add(f.claim_a.source_filename)
        if f.claim_b and f.claim_b.source_filename:
            docs.add(f.claim_b.source_filename)

        for d in docs:
            doc_counts[d] = doc_counts.get(d, 0) + 1

        flag_details.append({
            "id": f.id,
            "conflict_type": f.conflict_type,
            "description": f.description,
            "resolved": f.resolved,
            "claim_a_id": f.claim_a_id,
            "claim_b_id": f.claim_b_id,
            "source_files": list(docs),
        })

    by_type = [{"type": k, "count": v} for k, v in sorted(type_counts.items(), key=lambda x: -x[1])]
    by_doc = [{"filename": k, "count": v} for k, v in sorted(doc_counts.items(), key=lambda x: -x[1])]
    unresolved = sum(1 for f in flags if not f.resolved)
    resolved = len(flags) - unresolved

    by_resolution = [
        {"status": "unresolved", "count": unresolved},
        {"status": "resolved", "count": resolved},
    ]

    unres_type_counts: Dict[str, int] = {}
    res_type_counts: Dict[str, int] = {}
    for f in flags:
        if f.resolved:
            res_type_counts[f.conflict_type] = res_type_counts.get(f.conflict_type, 0) + 1
        else:
            unres_type_counts[f.conflict_type] = unres_type_counts.get(f.conflict_type, 0) + 1

    unresolved_by_type = [{"type": k, "count": v} for k, v in sorted(unres_type_counts.items(), key=lambda x: -x[1])]
    resolved_by_type = [{"type": k, "count": v} for k, v in sorted(res_type_counts.items(), key=lambda x: -x[1])]

    types_str = ", ".join(f"{item['type']} ({item['count']})" for item in by_type)
    summary = (
        f"Total flags: {len(flags)} ({unresolved} unresolved, {resolved} resolved). "
        f"Breakdown: {types_str}."
    )

    return {
        "total_conflicts": len(flags),
        "unresolved_conflicts": unresolved,
        "resolved_conflicts": resolved,
        "by_resolution_status": by_resolution,
        "by_conflict_type": by_type,
        "unresolved_by_type": unresolved_by_type,
        "resolved_by_type": resolved_by_type,
        "by_document": by_doc,
        "flags": flag_details,
        "summary": summary,
    }


# ============================================================================
# 6. Project Timeline
# ============================================================================

def get_project_timeline(
    db: Session,
    limit: int = 100,
    ascending: bool = True,
) -> Dict[str, Any]:
    """
    Retrieve unified chronological timeline combining events from Git commits,
    Chat messages, Task milestones, and Document uploads.
    """
    events: List[Dict[str, Any]] = []

    # 1. Document uploads
    files = db.query(models.UploadedFile).all()
    for f in files:
        dt_str = f.uploaded_at.strftime("%Y-%m-%d %H:%M:%S") if f.uploaded_at else "Unknown"
        events.append({
            "event_type": "document_upload",
            "source_id": f.id,
            "record_id": f"file-{f.id}",
            "original_timestamp": dt_str,
            "timestamp": dt_str,
            "date": _normalize_iso_date(None, f.uploaded_at),
            "title": f"Uploaded {f.filename}",
            "description": f"Source type: {f.source_type}, size: {(f.size_bytes / 1024):.1f} KB",
            "source_filename": f.filename,
            "is_synthetic": _is_synthetic(f.filename),
        })

    # 2. Evidence chunks (Git, Chat, Task)
    chunks = (
        db.query(models.EvidenceChunk, models.UploadedFile.filename)
        .join(models.UploadedFile, models.EvidenceChunk.file_id == models.UploadedFile.id)
        .filter(models.EvidenceChunk.source_type.in_(["git", "chat", "task"]))
        .all()
    )

    for ch, filename in chunks:
        dt_raw = ch.record_timestamp or ""
        date_iso = _normalize_iso_date(dt_raw)
        st = ch.source_type

        if st == "git":
            m_msg = re.search(r":\s*(.*?)(?:\s*\[Changed files:|$)", ch.text)
            msg = m_msg.group(1).strip() if m_msg else ch.text[:80]
            author = _clean_author_name(ch.author)
            events.append({
                "event_type": "git_commit",
                "source_id": ch.id,
                "record_id": ch.record_id or f"commit-{ch.id}",
                "original_timestamp": dt_raw,
                "timestamp": dt_raw or date_iso,
                "date": date_iso,
                "title": f"Git Commit {ch.record_id[:10] if ch.record_id else ''} by {author}",
                "description": msg,
                "source_filename": filename,
                "is_synthetic": _is_synthetic(filename, ch.text),
            })
        elif st == "chat":
            m_msg = re.search(r"\):\s*(.+)$", ch.text)
            msg = m_msg.group(1).strip() if m_msg else ch.text[:80]
            speaker = _clean_author_name(ch.author)
            events.append({
                "event_type": "chat_message",
                "source_id": ch.id,
                "record_id": ch.record_id or f"msg-{ch.id}",
                "original_timestamp": dt_raw,
                "timestamp": dt_raw or date_iso,
                "date": date_iso,
                "title": f"Chat from {speaker}",
                "description": msg,
                "source_filename": filename,
                "is_synthetic": _is_synthetic(filename, ch.text),
            })
        elif st == "task":
            m_status = re.search(r"\[([^\]]+)\]:", ch.text)
            status = m_status.group(1).strip() if m_status else "Task"
            m_title = re.search(r"\]:\s*(.*?)(?:\s*-\s*|\s*\(Assignee:|$)", ch.text)
            title = m_title.group(1).strip() if m_title else ch.text[:80]
            events.append({
                "event_type": "task_milestone",
                "source_id": ch.id,
                "record_id": ch.record_id or f"task-{ch.id}",
                "original_timestamp": dt_raw,
                "timestamp": dt_raw or date_iso,
                "date": date_iso,
                "title": f"Task {ch.record_id or ''} [{status}]: {title}",
                "description": ch.text[:120],
                "source_filename": filename,
                "is_synthetic": _is_synthetic(filename, ch.text),
            })

    # Sort events by timestamp string
    events.sort(key=lambda x: str(x.get("timestamp") or ""), reverse=not ascending)
    limited_events = events[:limit]

    summary = (
        f"Timeline contains {len(events)} total project event(s) "
        f"across Git commits, chat messages, task milestones, and file uploads."
    )

    return {
        "total_events": len(events),
        "events": limited_events,
        "summary": summary,
    }


# ============================================================================
# 7. Composite Project Summary
# ============================================================================

def get_project_dashboard_analytics(db: Session) -> Dict[str, Any]:
    """
    Composite high-level analytics snapshot combining all modules for chatbot overview questions.
    """
    tasks = get_task_analytics(db)
    git = get_git_analytics(db)
    claims = get_claims_analytics(db)
    evidence = get_evidence_analytics(db)
    conflicts = get_conflict_analytics(db)

    return {
        "tasks": tasks,
        "git": git,
        "claims": claims,
        "evidence": evidence,
        "conflicts": conflicts,
        "timestamp": datetime.utcnow().isoformat(),
    }
