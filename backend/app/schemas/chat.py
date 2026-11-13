"""
CogniTrace — Phase 3: Chatbot Schemas
backend/app/schemas/chat.py
"""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict, field_validator


class ChatCitationSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    source_filename: str
    source_type: Optional[str] = "document"
    chunk_id: Optional[int] = None
    claim_id: Optional[int] = None
    record_id: Optional[str] = None
    page_number: Optional[int] = None
    line_number: Optional[int] = None
    status: Optional[str] = None
    claim_type: Optional[str] = None
    original_timestamp: Optional[str] = None
    excerpt: str


class ChartSpecSchema(BaseModel):
    chart_type: str  # "bar", "pie", "line", "timeline"
    title: str
    x_key: str = "label"
    y_key: str = "value"
    data: List[Dict[str, Any]] = Field(default_factory=list)
    total: Optional[float] = None
    description: Optional[str] = None


class ChatMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="User natural language message")
    session_id: Optional[str] = Field(None, max_length=128, description="Legacy or alias chat session identifier")
    conversation_id: Optional[str] = Field(None, max_length=128, description="Persistent conversation identifier")
    client_id: Optional[str] = Field(None, max_length=128, description="Browser client identifier")

    @field_validator("message")
    @classmethod
    def message_must_not_be_blank(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Message cannot be empty or whitespace only")
        return cleaned

    @field_validator("session_id", "conversation_id", "client_id")
    @classmethod
    def id_must_be_valid(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("Identifier cannot be empty or whitespace only")
        return cleaned


class ChatMessageResponse(BaseModel):
    conversation_id: str
    session_id: str  # alias for backwards compatibility
    answer: str
    intent: str
    citations: List[ChatCitationSchema] = Field(default_factory=list)
    chart_spec: Optional[ChartSpecSchema] = None
    analytics_payload: Optional[Dict[str, Any]] = None
    follow_up_suggestions: List[str] = Field(default_factory=list)


class StoredChatMessageSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    conversation_id: str
    role: str
    content: str
    intent: Optional[str] = None
    citations: List[ChatCitationSchema] = Field(default_factory=list)
    chart_spec: Optional[ChartSpecSchema] = None
    follow_up_suggestions: List[str] = Field(default_factory=list)
    created_at: datetime


class ConversationSummarySchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0


class ConversationDetailSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    client_id: str
    title: str
    created_at: datetime
    updated_at: datetime
    messages: List[StoredChatMessageSchema] = Field(default_factory=list)


class CreateConversationRequest(BaseModel):
    client_id: str = Field(..., min_length=1, max_length=128)
    title: Optional[str] = Field(None, max_length=255)


class UpdateConversationRequest(BaseModel):
    title: str = Field(..., min_length=1, max_length=255)


class ChatSuggestionItem(BaseModel):
    category: str
    prompt: str
    description: Optional[str] = None
    target_intent: Optional[str] = None


class ChatSuggestionsResponse(BaseModel):
    suggestions: List[ChatSuggestionItem]
