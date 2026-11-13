"""
CogniTrace — Empty Database Handling & General Inquiries Tests
Tests assistant behavior when 0 documents exist and ensures general questions succeed.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import (
    Base,
    UploadedFile,
    EvidenceChunk,
    Claim,
    ClaimType,
    ClaimStatus,
    ConflictFlag,
    ParsingStatus,
)
from app.services import chat_assistant as ca


@pytest.fixture
def empty_db():
    """Clean, empty in-memory SQLite session with 0 files, 0 chunks, 0 claims."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def populated_db():
    """In-memory SQLite session with populated evidence, tasks, and claims."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    f = UploadedFile(
        id=1, filename="tasks.csv", content_type="text/csv",
        size_bytes=1024, status=ParsingStatus.completed, source_type="task"
    )
    session.add(f)
    session.flush()

    ch = EvidenceChunk(
        id=1, file_id=1, chunk_index=0,
        text="Task TASK-101 [Completed]: Implement JWT auth (Assignee: Priya)",
        source_type="task", record_id="TASK-101"
    )
    session.add(ch)

    cl = Claim(
        id=1, claim_text="JWT authentication is implemented.",
        claim_type=ClaimType.completed_feature, status=ClaimStatus.approved,
        source_file_id=1, source_filename="tasks.csv"
    )
    session.add(cl)
    session.commit()

    yield session
    session.close()


# ==============================================================================
# 1. Project status query with zero documents & zero chunks
# ==============================================================================

def test_project_status_query_with_zero_documents(empty_db):
    """When DB has zero uploaded documents, project status query returns friendly guidance."""
    resp = ca.ask_assistant(empty_db, "What is the current project status?", use_gemini=False)
    assert resp["intent"] == ca.INTENT_EMPTY_DATABASE
    assert "I don't have any project documents or evidence to analyse yet" in resp["answer"]
    assert "Please upload your project documents" in resp["answer"]
    assert "No Citation, No Assertion" in resp["answer"]
    assert len(resp["citations"]) == 0
    assert resp["analytics_payload"]["empty"] is True


# ==============================================================================
# 2. Project status query with zero claims and evidence chunks
# ==============================================================================

def test_project_status_query_with_zero_claims_and_evidence(empty_db):
    """Ensures no HTTP 500 or uncaught KeyError occurs when calculating zero claims & zero conflicts."""
    resp = ca.ask_assistant(empty_db, "Give me an overall project overview and summary", use_gemini=False)
    assert resp["intent"] == ca.INTENT_EMPTY_DATABASE
    assert "I don't have any project documents or evidence to analyse yet" in resp["answer"]
    assert len(resp["follow_up_suggestions"]) > 0


# ==============================================================================
# 3. General CogniTrace question with an empty database
# ==============================================================================

def test_general_cognitrace_question_with_empty_database(empty_db):
    """General questions about CogniTrace succeed even when the database is empty."""
    resp1 = ca.ask_assistant(empty_db, "What is CogniTrace?", use_gemini=False)
    assert resp1["intent"] == ca.INTENT_SYSTEM_INFO
    assert "About CogniTrace" in resp1["answer"]
    assert "No Citation, No Assertion" in resp1["answer"]

    resp2 = ca.ask_assistant(empty_db, "How does CogniTrace work?", use_gemini=False)
    assert resp2["intent"] == ca.INTENT_SYSTEM_INFO
    assert "Multi-Source Ingestion" in resp2["answer"]

    resp3 = ca.ask_assistant(empty_db, "What can you do?", use_gemini=False)
    assert resp3["intent"] == ca.INTENT_SYSTEM_INFO


# ==============================================================================
# 4. Project status query with populated evidence
# ==============================================================================

def test_project_status_query_with_populated_evidence(populated_db):
    """When evidence exists, assistant provides full evidence-grounded status."""
    resp = ca.ask_assistant(populated_db, "What is the current project status?", use_gemini=False)
    assert resp["intent"] == ca.INTENT_PROJECT_OVERVIEW
    assert "CogniTrace Project Status Overview" in resp["answer"]
    assert "TASK-101" in resp["answer"] or "1 unique task(s)" in resp["answer"]
    assert len(resp["citations"]) > 0


# ==============================================================================
# 5. Task status query with an empty database
# ==============================================================================

def test_task_status_query_with_empty_database(empty_db):
    """Task status query returns the empty database guidance when 0 documents exist."""
    resp = ca.ask_assistant(empty_db, "Which tasks are completed and pending?", use_gemini=False)
    assert resp["intent"] == ca.INTENT_EMPTY_DATABASE
    assert "I don't have any project documents or evidence to analyse yet" in resp["answer"]
    assert len(resp["citations"]) == 0
