from pydantic import BaseModel
from typing import Optional


class ImportResponse(BaseModel):
    file_id: int
    filename: str
    source_type: str
    status: str
    imported_count: int
    skipped_duplicates: int
    message: str
