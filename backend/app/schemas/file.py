from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime

class EvidenceChunkSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_id: int
    chunk_index: int
    text: str
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    json_path: Optional[str] = None
    source_type: str = "document"
    record_id: Optional[str] = None
    author: Optional[str] = None
    record_timestamp: Optional[str] = None

class FileMeta(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    filename: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    status: str
    error_message: Optional[str] = None
    source_type: str = "document"
    records_count: int = 0

class FileDetail(FileMeta):
    pass

class UploadResponse(BaseModel):
    uploaded: List[dict]

class DeleteResponse(BaseModel):
    deleted: bool
    id: int
