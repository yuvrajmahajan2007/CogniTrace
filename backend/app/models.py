from sqlalchemy import Column, Integer, String, DateTime, Enum, ForeignKey, Text, Boolean
from sqlalchemy.orm import relationship
from datetime import datetime
from enum import Enum as PyEnum
from .db import Base


class ParsingStatus(PyEnum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"


class ClaimStatus(PyEnum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class ClaimType(PyEnum):
    technology = "technology"
    architecture_decision = "architecture_decision"
    completed_feature = "completed_feature"
    pending_feature = "pending_feature"
    blocker_risk = "blocker_risk"
    dependency = "dependency"
    todo_fixme = "todo_fixme"
    project_decision = "project_decision"


class UploadedFile(Base):
    __tablename__ = "uploaded_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, nullable=False)
    content_type = Column(String, nullable=False)
    size_bytes = Column(Integer, nullable=False)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    status = Column(Enum(ParsingStatus), default=ParsingStatus.pending)
    error_message = Column(Text, nullable=True)
    source_type = Column(String, default="document", nullable=False)  # document, git, chat, task
    file_hash = Column(String, nullable=True, index=True)
    records_count = Column(Integer, default=0, nullable=False)

    evidence_chunks = relationship("EvidenceChunk", back_populates="file", cascade="all, delete-orphan")
    claims = relationship("Claim", back_populates="source_file", cascade="all, delete-orphan")


class EvidenceChunk(Base):
    __tablename__ = "evidence_chunks"

    id = Column(Integer, primary_key=True, index=True)
    file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False, index=True)
    chunk_index = Column(Integer, nullable=False)
    text = Column(Text, nullable=False)
    page_number = Column(Integer, nullable=True)  # PDF/DOCX page or paragraph
    line_number = Column(Integer, nullable=True)  # TXT/MD line / CSV row
    json_path = Column(String, nullable=True)    # JSON key path if applicable
    source_type = Column(String, default="document", nullable=False)
    record_id = Column(String, nullable=True, index=True)  # commit hash, task id, or message ref
    record_fingerprint = Column(String, nullable=True, index=True)
    author = Column(String, nullable=True)
    record_timestamp = Column(String, nullable=True)

    file = relationship("UploadedFile", back_populates="evidence_chunks")
    citations = relationship("Citation", back_populates="evidence_chunk", cascade="all, delete-orphan")


class Claim(Base):
    __tablename__ = "claims"

    id = Column(Integer, primary_key=True, index=True)
    claim_text = Column(Text, nullable=False)
    claim_type = Column(Enum(ClaimType), nullable=False, index=True)
    status = Column(Enum(ClaimStatus), default=ClaimStatus.pending, nullable=False, index=True)
    source_file_id = Column(Integer, ForeignKey("uploaded_files.id"), nullable=False, index=True)
    source_filename = Column(String, nullable=False)
    extraction_method = Column(String, default="rule_based", nullable=False)
    insufficient_evidence = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    source_file = relationship("UploadedFile", back_populates="claims")
    citations = relationship("Citation", back_populates="claim", cascade="all, delete-orphan")
    review_history = relationship("ReviewHistory", back_populates="claim", cascade="all, delete-orphan", order_by="ReviewHistory.reviewed_at.desc()")


class Citation(Base):
    __tablename__ = "citations"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    evidence_chunk_id = Column(Integer, ForeignKey("evidence_chunks.id"), nullable=False, index=True)
    filename = Column(String, nullable=False)
    page_number = Column(Integer, nullable=True)
    line_number = Column(Integer, nullable=True)
    json_path = Column(String, nullable=True)
    excerpt = Column(Text, nullable=False)

    claim = relationship("Claim", back_populates="citations")
    evidence_chunk = relationship("EvidenceChunk", back_populates="citations")


class ReviewHistory(Base):
    __tablename__ = "review_history"

    id = Column(Integer, primary_key=True, index=True)
    claim_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    action = Column(String, nullable=False)
    previous_text = Column(Text, nullable=True)
    new_text = Column(Text, nullable=True)
    previous_status = Column(String, nullable=True)
    new_status = Column(String, nullable=True)
    comment = Column(Text, nullable=True)
    reviewed_at = Column(DateTime, default=datetime.utcnow)

    claim = relationship("Claim", back_populates="review_history")


class ConflictFlag(Base):
    __tablename__ = "conflict_flags"

    id = Column(Integer, primary_key=True, index=True)
    claim_a_id = Column(Integer, ForeignKey("claims.id"), nullable=False, index=True)
    claim_b_id = Column(Integer, ForeignKey("claims.id"), nullable=True, index=True)
    conflict_type = Column(String, nullable=False)  # "contradiction" or "insufficient_evidence"
    description = Column(Text, nullable=False)
    resolved = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)

    claim_a = relationship("Claim", foreign_keys=[claim_a_id])
    claim_b = relationship("Claim", foreign_keys=[claim_b_id])


class HandoverReport(Base):
    __tablename__ = "handover_reports"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String, nullable=False)
    approved_claims_count = Column(Integer, default=0, nullable=False)
    conflicts_count = Column(Integer, default=0, nullable=False)
    source_files_count = Column(Integer, default=0, nullable=False)
    markdown_content = Column(Text, nullable=False)
    markdown_path = Column(String, nullable=False)
    pdf_path = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(String(64), primary_key=True, index=True)
    client_id = Column(String(128), nullable=False, index=True)
    title = Column(String(255), nullable=False, default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    messages = relationship(
        "ChatMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="ChatMessage.created_at.asc()"
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, index=True)
    conversation_id = Column(
        String(64),
        ForeignKey("conversations.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    role = Column(String(20), nullable=False)  # "user" or "assistant"
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    citations_json = Column(Text, nullable=True)
    chart_spec_json = Column(Text, nullable=True)
    follow_ups_json = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    conversation = relationship("Conversation", back_populates="messages")

