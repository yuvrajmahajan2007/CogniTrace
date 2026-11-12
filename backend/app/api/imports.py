from typing import List, Optional
from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from sqlalchemy.orm import Session
from ..db import SessionLocal
from .. import models
from ..schemas import file as file_schema
from ..schemas import import_source as import_schema
from ..services import multi_source_importer

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def _handle_import(
    source_type: str,
    file: UploadFile,
    db: Session,
) -> import_schema.ImportResponse:
    raw_bytes = await file.read()
    try:
        db_file, imported_count, skipped_duplicates = multi_source_importer.import_source_file(
            db=db,
            source_type=source_type,
            filename=file.filename or f"{source_type}_export",
            content_type=file.content_type or "application/octet-stream",
            raw_bytes=raw_bytes,
        )
    except FileExistsError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    msg = f"Imported {imported_count} {source_type} record(s) from '{db_file.filename}'."
    if skipped_duplicates > 0:
        msg += f" Skipped {skipped_duplicates} duplicate record(s)."

    return import_schema.ImportResponse(
        file_id=db_file.id,
        filename=db_file.filename,
        source_type=db_file.source_type,
        status=db_file.status.value if hasattr(db_file.status, "value") else str(db_file.status),
        imported_count=imported_count,
        skipped_duplicates=skipped_duplicates,
        message=msg,
    )


@router.post("/git", response_model=import_schema.ImportResponse)
async def import_git_activity(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await _handle_import("git", file, db)


@router.post("/chat", response_model=import_schema.ImportResponse)
async def import_chat_export(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await _handle_import("chat", file, db)


@router.post("/tasks", response_model=import_schema.ImportResponse)
async def import_task_records(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    return await _handle_import("task", file, db)


@router.get("", response_model=List[file_schema.FileMeta])
def list_imports(
    source_type: Optional[str] = Query(default=None),
    db: Session = Depends(get_db),
):
    query = db.query(models.UploadedFile)
    if source_type:
        query = query.filter(models.UploadedFile.source_type == source_type)
    else:
        query = query.filter(models.UploadedFile.source_type != "document")
    items = query.order_by(models.UploadedFile.uploaded_at.desc()).all()
    return [
        file_schema.FileMeta(
            id=f.id,
            filename=f.filename,
            content_type=f.content_type,
            size_bytes=f.size_bytes,
            uploaded_at=f.uploaded_at,
            status=f.status.value if hasattr(f.status, "value") else str(f.status),
            error_message=f.error_message,
            source_type=getattr(f, "source_type", "document"),
            records_count=getattr(f, "records_count", 0),
        )
        for f in items
    ]
