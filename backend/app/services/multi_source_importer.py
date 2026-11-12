import csv
import hashlib
import io
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session
from .. import models
from ..core.config import settings


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _record_fingerprint(source_type: str, record_id: Optional[str], text: str) -> str:
    norm_text = re.sub(r"\s+", " ", (text or "").strip().lower())
    raw = f"{source_type}::{record_id or ''}::{norm_text}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _pick(obj: Dict[str, Any], *keys: str) -> Optional[str]:
    lower_map = {str(k).strip().lower(): v for k, v in obj.items()}
    for key in keys:
        val = lower_map.get(key.lower())
        if val is not None and str(val).strip() != "":
            return str(val).strip()
    return None


def _parse_git_txt(text: str) -> List[dict]:
    records: List[dict] = []
    # 1. Standard `git log` blocks starting with `commit <hash>`
    blocks = re.split(r"(?m)^commit\s+", text.strip())
    if len(blocks) > 1 or text.strip().startswith("commit "):
        for idx, block in enumerate(blocks):
            block = block.strip()
            if not block:
                continue
            lines = block.splitlines()
            commit_hash = lines[0].strip().split()[0]
            author = None
            date_str = None
            msg_lines: List[str] = []
            files_list: List[str] = []
            in_files = False

            for line in lines[1:]:
                stripped = line.strip()
                if stripped.lower().startswith("author:"):
                    author = stripped.split(":", 1)[1].strip()
                elif stripped.lower().startswith("date:"):
                    date_str = stripped.split(":", 1)[1].strip()
                elif stripped.lower().startswith("files:") or stripped.lower().startswith("changed files:"):
                    in_files = True
                    rest = stripped.split(":", 1)[1].strip()
                    if rest:
                        files_list.append(rest)
                elif in_files and stripped:
                    files_list.append(stripped)
                elif stripped:
                    msg_lines.append(stripped)

            message = " ".join(msg_lines).strip()
            if not message and not commit_hash:
                continue
            formatted = f"Git Commit {commit_hash[:12]}"
            if author:
                formatted += f" by {author}"
            if date_str:
                formatted += f" on {date_str}"
            formatted += f": {message}"
            if files_list:
                formatted += f" [Changed files: {', '.join(files_list)}]"

            records.append(
                {
                    "record_id": commit_hash,
                    "author": author,
                    "record_timestamp": date_str,
                    "line_number": idx + 1,
                    "text": formatted,
                }
            )
        if records:
            return records

    # 2. Compact pipe-delimited or `hash - message` lines
    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        if "|" in line:
            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 4:
                commit_hash, author, date_str, message = parts[0], parts[1], parts[2], parts[3]
                changed = parts[4] if len(parts) > 4 else ""
                formatted = f"Git Commit {commit_hash[:12]} by {author} on {date_str}: {message}"
                if changed:
                    formatted += f" [Changed files: {changed}]"
                records.append(
                    {
                        "record_id": commit_hash,
                        "author": author,
                        "record_timestamp": date_str,
                        "line_number": line_num,
                        "text": formatted,
                    }
                )
    return records


def _parse_git_csv(text: str) -> List[dict]:
    records: List[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return records
    for row_num, row in enumerate(reader, start=2):
        commit_hash = _pick(row, "commit_hash", "hash", "sha", "commit", "commit_id")
        author = _pick(row, "author", "committer", "user", "name")
        date_str = _pick(row, "commit_date", "date", "timestamp", "authored_at")
        message = _pick(row, "message", "commit_message", "subject", "title", "description")
        files = _pick(row, "changed_files", "files")
        if not message:
            continue
        rec_id = commit_hash or f"row-{row_num}"
        formatted = f"Git Commit {rec_id[:12]}"
        if author:
            formatted += f" by {author}"
        if date_str:
            formatted += f" on {date_str}"
        formatted += f": {message}"
        if files:
            formatted += f" [Changed files: {files}]"
        records.append(
            {
                "record_id": rec_id,
                "author": author,
                "record_timestamp": date_str,
                "line_number": row_num,
                "text": formatted,
            }
        )
    return records


def _parse_git_json(text: str) -> List[dict]:
    data = json.loads(text)
    items = data if isinstance(data, list) else data.get("commits", []) if isinstance(data, dict) else []
    records: List[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        commit_hash = _pick(item, "commit_hash", "hash", "sha", "id", "commit")
        author = _pick(item, "author", "committer", "user")
        date_str = _pick(item, "commit_date", "date", "timestamp")
        message = _pick(item, "message", "commit_message", "subject", "title")
        raw_files = item.get("changed_files") or item.get("files")
        files_str = ", ".join(str(x) for x in raw_files) if isinstance(raw_files, list) else (str(raw_files) if raw_files else "")
        if not message:
            continue
        rec_id = commit_hash or f"commit-{idx}"
        formatted = f"Git Commit {rec_id[:12]}"
        if author:
            formatted += f" by {author}"
        if date_str:
            formatted += f" on {date_str}"
        formatted += f": {message}"
        if files_str:
            formatted += f" [Changed files: {files_str}]"
        records.append(
            {
                "record_id": rec_id,
                "author": author,
                "record_timestamp": date_str,
                "json_path": f"$[{idx}]",
                "text": formatted,
            }
        )
    return records


def _parse_chat_txt(text: str) -> List[dict]:
    records: List[dict] = []
    # Matches `[2026-11-10 10:15] Alice: message` or `2026-11-10 10:15 - Alice: message`
    ts_pattern = re.compile(r"^\[?(\d{4}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?)?)\]?\s*[-–]?\s*([^:]{1,60}):\s+(.+)$")
    plain_pattern = re.compile(r"^([^:]{1,50}):\s+(.+)$")

    for line_num, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        m_ts = ts_pattern.match(line)
        if m_ts:
            ts, speaker, msg = m_ts.group(1).strip(), m_ts.group(2).strip(), m_ts.group(3).strip()
        else:
            m_plain = plain_pattern.match(line)
            if not m_plain:
                continue
            ts = None
            speaker, msg = m_plain.group(1).strip(), m_plain.group(2).strip()

        rec_id = f"msg-{line_num}"
        formatted = f"Chat ({speaker}" + (f" at {ts}" if ts else "") + f"): {msg}"
        records.append(
            {
                "record_id": rec_id,
                "author": speaker,
                "record_timestamp": ts,
                "line_number": line_num,
                "text": formatted,
            }
        )
    return records


def _parse_chat_json(text: str) -> List[dict]:
    data = json.loads(text)
    items = data if isinstance(data, list) else data.get("messages", []) if isinstance(data, dict) else []
    records: List[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        rec_id = _pick(item, "id", "message_id", "msg_id") or f"msg-{idx + 1}"
        speaker = _pick(item, "speaker", "author", "sender", "user", "name") or "Unknown"
        ts = _pick(item, "timestamp", "ts", "date", "time", "created_at")
        msg = _pick(item, "message", "text", "content", "body")
        if not msg:
            continue
        formatted = f"Chat ({speaker}" + (f" at {ts}" if ts else "") + f"): {msg}"
        records.append(
            {
                "record_id": rec_id,
                "author": speaker,
                "record_timestamp": ts,
                "json_path": f"$[{idx}]",
                "text": formatted,
            }
        )
    return records


def _format_task_text(
    task_id: str,
    title: str,
    status: Optional[str],
    description: Optional[str],
    assignee: Optional[str],
    priority: Optional[str],
    due_date: Optional[str],
) -> str:
    status_label = status or "unspecified"
    parts = [f"Task {task_id} [{status_label}]: {title}"]
    if description:
        parts.append(description)
    meta = []
    if assignee:
        meta.append(f"Assignee: {assignee}")
    if priority:
        meta.append(f"Priority: {priority}")
    if due_date:
        meta.append(f"Due: {due_date}")
    if meta:
        parts.append(f"({', '.join(meta)})")
    return " - ".join(parts[:2]) + (f" {parts[2]}" if len(parts) > 2 else "")


def _parse_tasks_csv(text: str) -> List[dict]:
    records: List[dict] = []
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return records
    for row_num, row in enumerate(reader, start=2):
        task_id = _pick(row, "task_id", "id", "key", "issue_id") or f"TASK-{row_num - 1}"
        title = _pick(row, "title", "summary", "name", "subject")
        description = _pick(row, "description", "details", "notes")
        status = _pick(row, "status", "state")
        assignee = _pick(row, "assignee", "owner", "assigned_to")
        priority = _pick(row, "priority", "severity")
        due_date = _pick(row, "due_date", "due", "deadline")
        if not title and not description:
            continue
        formatted = _format_task_text(
            task_id=task_id,
            title=title or description or "",
            status=status,
            description=description if title else None,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
        )
        records.append(
            {
                "record_id": task_id,
                "author": assignee,
                "record_timestamp": due_date,
                "line_number": row_num,
                "text": formatted,
            }
        )
    return records


def _parse_tasks_json(text: str) -> List[dict]:
    data = json.loads(text)
    if isinstance(data, list):
        items = data
    elif isinstance(data, dict):
        items = data.get("tasks") or data.get("issues") or []
    else:
        items = []

    records: List[dict] = []
    for idx, item in enumerate(items):
        if not isinstance(item, dict):
            continue
        task_id = _pick(item, "task_id", "id", "key", "issue_id") or f"TASK-{idx + 1}"
        title = _pick(item, "title", "summary", "name", "subject")
        description = _pick(item, "description", "details", "notes")
        status = _pick(item, "status", "state")
        assignee = _pick(item, "assignee", "owner", "assigned_to")
        priority = _pick(item, "priority", "severity")
        due_date = _pick(item, "due_date", "due", "deadline")
        if not title and not description:
            continue
        formatted = _format_task_text(
            task_id=task_id,
            title=title or description or "",
            status=status,
            description=description if title else None,
            assignee=assignee,
            priority=priority,
            due_date=due_date,
        )
        records.append(
            {
                "record_id": task_id,
                "author": assignee,
                "record_timestamp": due_date,
                "json_path": f"$[{idx}]",
                "text": formatted,
            }
        )
    return records


ALLOWED_EXTENSIONS_BY_SOURCE = {
    "git": {"txt", "csv", "json"},
    "chat": {"txt", "json"},
    "task": {"csv", "json"},
}


def import_source_file(
    db: Session,
    source_type: str,
    filename: str,
    content_type: str,
    raw_bytes: bytes,
) -> Tuple[models.UploadedFile, int, int]:
    """
    Validate, deduplicate, parse, and persist Git, Chat, or Task records into
    UploadedFile + EvidenceChunk rows.
    Returns (db_file, imported_count, skipped_duplicates).
    """
    if source_type not in ALLOWED_EXTENSIONS_BY_SOURCE:
        raise ValueError(f"Unsupported source type: {source_type}")

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    allowed = ALLOWED_EXTENSIONS_BY_SOURCE[source_type]
    if ext not in allowed:
        raise ValueError(
            f"Unsupported file extension '.{ext}' for {source_type} import. Allowed: {', '.join(sorted(allowed))}"
        )

    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if len(raw_bytes) > max_bytes:
        raise ValueError(f"File exceeds maximum size of {settings.MAX_UPLOAD_SIZE_MB} MB")

    file_hash = _sha256_bytes(raw_bytes)
    existing_file = (
        db.query(models.UploadedFile)
        .filter(
            models.UploadedFile.file_hash == file_hash,
            models.UploadedFile.source_type == source_type,
            models.UploadedFile.status == models.ParsingStatus.completed,
        )
        .first()
    )
    if existing_file:
        raise FileExistsError(
            f"Duplicate {source_type} export: '{filename}' has already been imported as '{existing_file.filename}' (file #{existing_file.id})."
        )

    decoded = raw_bytes.decode("utf-8", errors="replace")
    try:
        if source_type == "git":
            if ext == "txt":
                parsed_records = _parse_git_txt(decoded)
            elif ext == "csv":
                parsed_records = _parse_git_csv(decoded)
            else:
                parsed_records = _parse_git_json(decoded)
        elif source_type == "chat":
            if ext == "txt":
                parsed_records = _parse_chat_txt(decoded)
            else:
                parsed_records = _parse_chat_json(decoded)
        else:  # task
            if ext == "csv":
                parsed_records = _parse_tasks_csv(decoded)
            else:
                parsed_records = _parse_tasks_json(decoded)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in {filename}: {exc}") from exc

    if not parsed_records:
        raise ValueError(
            f"No valid {source_type} records found in '{filename}'. Verify the file structure."
        )

    # Save physical file copy
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    safe_name = os.path.basename(filename)
    disk_path = os.path.join(settings.UPLOAD_DIR, safe_name)
    counter = 1
    base, ext_dot = os.path.splitext(safe_name)
    while os.path.exists(disk_path):
        disk_path = os.path.join(settings.UPLOAD_DIR, f"{base}_{counter}{ext_dot}")
        counter += 1
    with open(disk_path, "wb") as f:
        f.write(raw_bytes)

    db_file = models.UploadedFile(
        filename=filename,
        content_type=content_type or "application/octet-stream",
        size_bytes=len(raw_bytes),
        status=models.ParsingStatus.completed,
        source_type=source_type,
        file_hash=file_hash,
        records_count=0,
    )
    db.add(db_file)
    db.flush()

    existing_fps = {
        row[0]
        for row in db.query(models.EvidenceChunk.record_fingerprint)
        .filter(models.EvidenceChunk.record_fingerprint.isnot(None))
        .all()
    }

    imported_count = 0
    skipped_duplicates = 0
    for idx, rec in enumerate(parsed_records):
        fp = _record_fingerprint(source_type, rec.get("record_id"), rec["text"])
        if fp in existing_fps:
            skipped_duplicates += 1
            continue
        existing_fps.add(fp)

        chunk = models.EvidenceChunk(
            file_id=db_file.id,
            chunk_index=imported_count,
            text=rec["text"],
            line_number=rec.get("line_number"),
            json_path=rec.get("json_path"),
            source_type=source_type,
            record_id=rec.get("record_id"),
            record_fingerprint=fp,
            author=rec.get("author"),
            record_timestamp=rec.get("record_timestamp"),
        )
        db.add(chunk)
        imported_count += 1

    db_file.records_count = imported_count
    db.commit()
    db.refresh(db_file)
    return db_file, imported_count, skipped_duplicates
