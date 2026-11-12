import os
import json
import csv
from typing import List
from ..db import SessionLocal
from .. import models
from ..core import config
import fitz  # PyMuPDF
import docx

CHUNK_SIZE = 1000  # characters per evidence chunk

def _save_chunks(file_id: int, chunks: List[dict]):
    db = SessionLocal()
    try:
        for idx, chunk in enumerate(chunks):
            evidence = models.EvidenceChunk(
                file_id=file_id,
                chunk_index=idx,
                text=chunk["text"],
                page_number=chunk.get("page_number"),
                line_number=chunk.get("line_number"),
                json_path=chunk.get("json_path"),
            )
            db.add(evidence)
        db.commit()
    finally:
        db.close()

def _split_into_chunks(text: str, **meta) -> List[dict]:
    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + CHUNK_SIZE, n)
        if end < n:
            # Prefer snapping back to a newline or sentence/whitespace boundary
            window = text[start:end]
            nl = window.rfind("\n")
            sp = window.rfind(" ")
            if nl > CHUNK_SIZE // 2:
                end = start + nl + 1
            elif sp > CHUNK_SIZE // 2:
                end = start + sp + 1
        chunk_text = text[start:end]
        if chunk_text.strip():
            chunk = {"text": chunk_text}
            chunk.update(meta)
            chunks.append(chunk)
        start = end
    return chunks

def parse_file(file_id: int, file_path: str):
    # Update status to processing
    db = SessionLocal()
    db_file = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    if not db_file:
        db.close()
        return
    db_file.status = models.ParsingStatus.processing
    db.commit()
    db.close()

    ext = os.path.splitext(file_path)[1].lower()
    chunks = []
    error = None
    try:
        if ext == ".pdf":
            doc = fitz.open(file_path)
            if doc.page_count == 0:
                error = "Empty PDF"
            else:
                for page_num, page in enumerate(doc, start=1):
                    text = page.get_text()
                    if not text.strip():
                        continue
                    page_chunks = _split_into_chunks(text, page_number=page_num)
                    chunks.extend(page_chunks)
        elif ext == ".docx":
            doc = docx.Document(file_path)
            for para_idx, para in enumerate(doc.paragraphs, start=1):
                text = para.text
                if text:
                    para_chunks = _split_into_chunks(text, page_number=para_idx)
                    chunks.extend(para_chunks)
        elif ext in {".txt", ".md"}:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                for line_num, line in enumerate(f, start=1):
                    line = line.rstrip("\n")
                    if line:
                        line_chunks = _split_into_chunks(line, line_number=line_num)
                        chunks.extend(line_chunks)
        elif ext == ".csv":
            with open(file_path, newline="", encoding="utf-8", errors="ignore") as csvfile:
                reader = csv.reader(csvfile)
                for row_num, row in enumerate(reader, start=1):
                    row_text = ", ".join(row)
                    if row_text:
                        row_chunks = _split_into_chunks(row_text, line_number=row_num)
                        chunks.extend(row_chunks)
        elif ext == ".json":
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                data = json.load(f)
            def _walk(obj, path=""):
                if isinstance(obj, dict):
                    for k, v in obj.items():
                        _walk(v, f"{path}/{k}" if path else f"/{k}")
                elif isinstance(obj, list):
                    for i, v in enumerate(obj):
                        _walk(v, f"{path}[{i}]")
                else:
                    txt = str(obj)
                    if txt:
                        leaf_chunks = _split_into_chunks(txt, json_path=path)
                        chunks.extend(leaf_chunks)
            _walk(data)
        else:
            error = f"Unsupported extension {ext}"
    except Exception as e:
        error = str(e)

    db = SessionLocal()
    db_file = db.query(models.UploadedFile).filter(models.UploadedFile.id == file_id).first()
    if db_file:
        if error:
            db_file.status = models.ParsingStatus.failed
            db_file.error_message = error
        else:
            db_file.status = models.ParsingStatus.completed
            if chunks:
                _save_chunks(file_id, chunks)
        db.commit()
    db.close()
