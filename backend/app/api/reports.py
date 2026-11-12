import os
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from ..db import SessionLocal
from .. import models
from ..schemas import report as report_schema
from ..services import report_generator

router = APIRouter()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


@router.post("/generate", response_model=report_schema.ReportDetailSchema)
def generate_report(
    payload: Optional[report_schema.ReportGenerateRequest] = None,
    db: Session = Depends(get_db),
):
    req = payload or report_schema.ReportGenerateRequest()
    report = report_generator.generate_handover_report(db=db, title=req.title)
    return report_schema.ReportDetailSchema.model_validate(report)


@router.get("", response_model=List[report_schema.ReportMetaSchema])
def list_reports(db: Session = Depends(get_db)):
    reports = (
        db.query(models.HandoverReport)
        .order_by(models.HandoverReport.created_at.desc(), models.HandoverReport.id.desc())
        .all()
    )
    return [report_schema.ReportMetaSchema.model_validate(r) for r in reports]


@router.get("/{report_id}", response_model=report_schema.ReportDetailSchema)
def get_report(report_id: int, db: Session = Depends(get_db)):
    report = (
        db.query(models.HandoverReport)
        .filter(models.HandoverReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report_schema.ReportDetailSchema.model_validate(report)


@router.get("/{report_id}/download")
def download_report(
    report_id: int,
    format: str = Query(default="pdf", pattern="^(pdf|markdown|md)$"),
    db: Session = Depends(get_db),
):
    report = (
        db.query(models.HandoverReport)
        .filter(models.HandoverReport.id == report_id)
        .first()
    )
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")

    if format == "pdf":
        if not os.path.exists(report.pdf_path):
            raise HTTPException(status_code=404, detail="PDF report file not found on disk")
        return FileResponse(
            path=report.pdf_path,
            media_type="application/pdf",
            filename=f"cognitrace_handover_report_{report.id}.pdf",
        )

    if not os.path.exists(report.markdown_path):
        raise HTTPException(status_code=404, detail="Markdown report file not found on disk")
    return FileResponse(
        path=report.markdown_path,
        media_type="text/markdown; charset=utf-8",
        filename=f"cognitrace_handover_report_{report.id}.md",
    )
