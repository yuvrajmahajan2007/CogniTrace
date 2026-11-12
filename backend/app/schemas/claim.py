from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional
from datetime import datetime


class CitationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    evidence_chunk_id: int
    filename: str
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    json_path: Optional[str] = None
    excerpt: str
    surrounding_context: Optional[str] = None
    source_type: Optional[str] = "document"
    record_id: Optional[str] = None
    author: Optional[str] = None
    record_timestamp: Optional[str] = None


class ReviewHistorySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_id: int
    action: str
    previous_text: Optional[str] = None
    new_text: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    comment: Optional[str] = None
    reviewed_at: datetime


class ConflictBriefSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_a_id: int
    claim_b_id: Optional[int] = None
    conflict_type: str
    description: str
    resolved: bool
    created_at: datetime


class ClaimSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_text: str
    claim_type: str
    status: str
    source_file_id: int
    source_filename: str
    extraction_method: str
    insufficient_evidence: bool
    created_at: datetime
    updated_at: datetime
    citations: List[CitationSchema] = []
    review_history: List[ReviewHistorySchema] = []


class ClaimGenerateRequest(BaseModel):
    use_gemini: bool = False
    clear_existing: bool = False


class ClaimGenerateResponse(BaseModel):
    generated_count: int
    skipped_duplicates: int
    conflicts_detected: int
    insufficient_evidence_flagged: int
    extraction_method: str
    message: str


class ClaimUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, description="pending, approved, or rejected")
    claim_text: Optional[str] = None
    comment: Optional[str] = None


class ClaimBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_text: str
    claim_type: str
    status: str
    source_filename: str


class ConflictDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    claim_a_id: int
    claim_b_id: Optional[int] = None
    conflict_type: str
    description: str
    resolved: bool
    created_at: datetime
    claim_a: Optional[ClaimBrief] = None
    claim_b: Optional[ClaimBrief] = None


class ClaimStatsSchema(BaseModel):
    total_claims: int
    pending_claims: int
    approved_claims: int
    rejected_claims: int
    total_conflicts: int
    unresolved_conflicts: int
    insufficient_evidence_count: int
