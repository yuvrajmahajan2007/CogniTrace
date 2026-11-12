from pydantic import BaseModel, ConfigDict
from typing import Optional
from datetime import datetime


class ReportGenerateRequest(BaseModel):
    title: Optional[str] = "CogniTrace Project Handover Report"


class ReportMetaSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    approved_claims_count: int
    conflicts_count: int
    source_files_count: int
    created_at: datetime


class ReportDetailSchema(ReportMetaSchema):
    markdown_content: str
