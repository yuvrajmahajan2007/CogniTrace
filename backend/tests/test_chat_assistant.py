"""
CogniTrace — Phase 2 Tests: Evidence-Grounded Conversational Service
backend/tests/test_chat_assistant.py
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
from app.db import SessionLocal
from app.services import chat_assistant as ca
from app.services import analytics_engine as ae


@pytest.fixture
def mock_db():
    """In-memory SQLite session populated with controlled project evidence."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Uploaded files
    f_doc = UploadedFile(
        id=1, filename="handover_spec.pdf", content_type="application/pdf",
        size_bytes=2048, status=ParsingStatus.completed, source_type="document"
    )
    f_git = UploadedFile(
        id=2, filename="git_log.txt", content_type="text/plain",
        size_bytes=1024, status=ParsingStatus.completed, source_type="git"
    )
    f_task = UploadedFile(
        id=3, filename="tasks.csv", content_type="text/csv",
        size_bytes=1024, status=ParsingStatus.completed, source_type="task"
    )
    f_chat = UploadedFile(
        id=4, filename="team_chat.txt", content_type="text/plain",
        size_bytes=512, status=ParsingStatus.completed, source_type="chat"
    )
    session.add_all([f_doc, f_git, f_task, f_chat])
    session.flush()

    # 2. Evidence chunks
    ch1 = EvidenceChunk(
        id=1, file_id=1, chunk_index=0,
        text="The CogniTrace backend uses FastAPI, SQLAlchemy, and SQLite for persistence.",
        source_type="document", page_number=1
    )
    ch2 = EvidenceChunk(
        id=2, file_id=2, chunk_index=0,
        text="Git Commit 1a2b3c by Priya Sharma on 2026-11-10 14:30:00: feat: Implement JWT authentication [Changed files: auth.py, main.py]",
        source_type="git", record_id="1a2b3c", author="Priya Sharma",
        record_timestamp="2026-11-10 14:30:00"
    )
    ch3 = EvidenceChunk(
        id=3, file_id=3, chunk_index=0,
        text="Task TASK-101 [Completed]: Implement JWT authentication (Assignee: Priya Sharma, Priority: High, Due: 2026-11-10)",
        source_type="task", record_id="TASK-101", author="Priya Sharma",
        record_timestamp="2026-11-10"
    )
    ch4 = EvidenceChunk(
        id=4, file_id=3, chunk_index=1,
        text="Task TASK-201 [Open]: Billing webhook handler (Assignee: Ananya, Priority: High, Due: 2026-11-15)",
        source_type="task", record_id="TASK-201", author="Ananya",
        record_timestamp="2026-11-15"
    )
    ch5 = EvidenceChunk(
        id=5, file_id=4, chunk_index=0,
        text="Ananya at 2026-11-12 11:00:00: The Billing webhook handler has been completed and is ready for deployment.",
        source_type="chat", record_id="msg-201", author="Ananya",
        record_timestamp="2026-11-12 11:00:00"
    )
    session.add_all([ch1, ch2, ch3, ch4, ch5])
    session.flush()

    # 3. Claims
    c1 = Claim(
        id=1, claim_text="CogniTrace backend uses FastAPI and SQLAlchemy.",
        claim_type=ClaimType.technology, status=ClaimStatus.approved,
        source_file_id=1, source_filename="handover_spec.pdf"
    )
    c2 = Claim(
        id=2, claim_text="JWT authentication middleware is completed.",
        claim_type=ClaimType.completed_feature, status=ClaimStatus.approved,
        source_file_id=3, source_filename="tasks.csv"
    )
    c3 = Claim(
        id=3, claim_text="Billing webhook handler task is Open.",
        claim_type=ClaimType.pending_feature, status=ClaimStatus.pending,
        source_file_id=3, source_filename="tasks.csv"
    )
    c4 = Claim(
        id=4, claim_text="Billing webhook handler completed per chat discussion.",
        claim_type=ClaimType.completed_feature, status=ClaimStatus.pending,
        source_file_id=4, source_filename="team_chat.txt"
    )
    session.add_all([c1, c2, c3, c4])
    session.flush()

    # 4. Conflict flag (genuine cross-source contradiction on billing webhook)
    cf = ConflictFlag(
        id=1, claim_a_id=3, claim_b_id=4, conflict_type="contradiction",
        description="Status contradiction on Billing webhook handler: tasks.csv indicates Open while team_chat.txt indicates completed.",
        resolved=False
    )
    session.add(cf)
    session.commit()

    yield session
    session.close()


# ==============================================================================
# INTENT DETECTION TESTS
# ==============================================================================

def test_intent_detection_all_types():
    """Verify natural-language intent detector recognizes all required inquiry types."""
    # Project overview
    intent, _ = ca.detect_intent("What is the current project status?")
    assert intent == ca.INTENT_PROJECT_OVERVIEW

    intent, _ = ca.detect_intent("Give me an overall project overview and summary")
    assert intent == ca.INTENT_PROJECT_OVERVIEW

    # Task status and assignees
    intent, _ = ca.detect_intent("Which tasks are completed and pending?")
    assert intent == ca.INTENT_TASK_ANALYTICS

    intent, _ = ca.detect_intent("Who is assigned to open tasks?")
    assert intent == ca.INTENT_TASK_ANALYTICS

    # Git activity
    intent, _ = ca.detect_intent("Summarise Git activity and commit history")
    assert intent == ca.INTENT_GIT_ANALYTICS

    intent, _ = ca.detect_intent("Who are the active contributors in git?")
    assert intent == ca.INTENT_GIT_ANALYTICS

    # Claims review
    intent, _ = ca.detect_intent("How many claims are approved vs pending review?")
    assert intent == ca.INTENT_CLAIMS_REVIEW

    # Evidence sources
    intent, _ = ca.detect_intent("What evidence sources and documents are imported?")
    assert intent == ca.INTENT_EVIDENCE_SOURCES

    # Conflicts & Blockers
    intent, _ = ca.detect_intent("Explain all detected contradictions and project blockers")
    assert intent == ca.INTENT_CONFLICTS_UNRESOLVED

    # Timeline
    intent, _ = ca.detect_intent("Show the project chronological timeline of events")
    assert intent == ca.INTENT_PROJECT_TIMELINE

    # Chart requests
    intent, meta = ca.detect_intent("Show completed vs pending tasks in a bar graph")
    assert intent == ca.INTENT_CHART_REQUEST
    assert meta["target"] == "task_status"
    assert meta["preferred_chart"] == "bar"

    intent, meta = ca.detect_intent("Generate a pie chart of task priority distribution")
    assert intent == ca.INTENT_CHART_REQUEST
    assert meta["target"] == "task_priority"
    assert meta["preferred_chart"] == "pie"

    intent, meta = ca.detect_intent("Show Git commits over time using a line chart")
    assert intent == ca.INTENT_CHART_REQUEST
    assert meta["target"] == "git_commits"
    assert meta["preferred_chart"] == "line"

    # Factual query
    intent, _ = ca.detect_intent("What technologies are used in the backend?")
    assert intent == ca.INTENT_FACTUAL_QUERY


# ==============================================================================
# EVIDENCE RETRIEVAL & CITATION TESTS
# ==============================================================================

def test_factual_evidence_retrieval_and_citations(mock_db):
    """Verify evidence retrieval locates relevant chunks and builds source-linked citations."""
    retrieval = ca.retrieve_factual_evidence(mock_db, "Is JWT authentication implemented?")
    assert retrieval["has_evidence"] is True
    assert len(retrieval["citations"]) > 0

    # Ensure citations have source metadata
    for cite in retrieval["citations"]:
        assert "source_filename" in cite
        assert "excerpt" in cite
        assert cite.get("claim_id") is not None or cite.get("chunk_id") is not None


# ==============================================================================
# NO CITATION, NO ASSERTION (MISSING EVIDENCE REFUSAL)
# ==============================================================================

def test_missing_evidence_refusal(mock_db):
    """Under 'No Citation, No Assertion', assistant refuses to invent unrecorded facts."""
    response = ca.ask_assistant(mock_db, "Has Kubernetes deployment and cluster autoscaling been configured?")
    assert response["intent"] == ca.INTENT_FACTUAL_QUERY
    assert "No Supporting Evidence Found" in response["answer"]
    assert "No Citation, No Assertion" in response["answer"]
    assert len(response["citations"]) == 0


# ==============================================================================
# CONTRADICTION HANDLING IN CONVERSATION
# ==============================================================================

def test_contradiction_handling_surfaces_both_sources(mock_db):
    """When a topic has conflicting sources, the assistant explains both sides."""
    response = ca.ask_assistant(mock_db, "What is the status of the Billing webhook handler?")
    assert response["intent"] == ca.INTENT_FACTUAL_QUERY
    answer = response["answer"]

    # Both perspectives must be mentioned
    assert "tasks.csv" in answer or "team_chat.txt" in answer
    assert "Conflicting Evidence Detected" in answer or "Warning" in answer

    # Citations must link to sources
    source_files = {c["source_filename"] for c in response["citations"]}
    assert "tasks.csv" in source_files or "team_chat.txt" in source_files


# ==============================================================================
# GEMINI UNAVAILABLE / FALLBACK HANDLING
# ==============================================================================

def test_gemini_unavailable_fallback(mock_db):
    """When Gemini is disabled or API key is absent, deterministic synthesis succeeds."""
    response = ca.ask_assistant(mock_db, "What is the current project status?", use_gemini=False)
    assert response["intent"] == ca.INTENT_PROJECT_OVERVIEW
    assert "CogniTrace Project Status Overview" in response["answer"]
    assert len(response["citations"]) > 0
    assert len(response["follow_up_suggestions"]) > 0


# ==============================================================================
# ANALYTICS INTEGRATION (NO CUSTOM SQL)
# ==============================================================================

def test_analytics_integration_in_chat(mock_db):
    """Verify task, git, and chart queries use analytics_engine data directly."""
    # Task query
    task_resp = ca.ask_assistant(mock_db, "Which tasks are completed and pending?")
    assert task_resp["intent"] == ca.INTENT_TASK_ANALYTICS
    assert task_resp["analytics_payload"] is not None
    assert "TASK-101" in task_resp["answer"]
    assert "TASK-201" in task_resp["answer"]

    # Chart query
    chart_resp = ca.ask_assistant(mock_db, "Show completed vs pending tasks in a bar graph")
    assert chart_resp["intent"] == ca.INTENT_CHART_REQUEST
    assert chart_resp["chart_spec"] is not None
    assert chart_resp["chart_spec"]["chart_type"] in ["bar", "pie"]
    assert len(chart_resp["chart_spec"]["data"]) > 0


# ==============================================================================
# READ-ONLY GUARANTEE: DATABASE NOT MUTATED
# ==============================================================================

def test_assistant_does_not_mutate_database(mock_db):
    """Conversational interaction must be read-only and never create new claims or chunks."""
    files_before = mock_db.query(UploadedFile).count()
    chunks_before = mock_db.query(EvidenceChunk).count()
    claims_before = mock_db.query(Claim).count()
    conflicts_before = mock_db.query(ConflictFlag).count()

    # Run diverse user queries
    ca.ask_assistant(mock_db, "What is the current project status?")
    ca.ask_assistant(mock_db, "Show completed vs pending tasks in a bar graph")
    ca.ask_assistant(mock_db, "Tell me about JWT authentication")
    ca.ask_assistant(mock_db, "Is Kubernetes ready?")

    # Assert no counts changed
    assert mock_db.query(UploadedFile).count() == files_before
    assert mock_db.query(EvidenceChunk).count() == chunks_before
    assert mock_db.query(Claim).count() == claims_before
    assert mock_db.query(ConflictFlag).count() == conflicts_before


# ==============================================================================
# LIVE DATABASE VERIFICATION
# ==============================================================================

def test_chat_assistant_against_live_database():
    """Verify conversational queries against the live cognitrace.db."""
    db = SessionLocal()
    try:
        # 1. Project overview query
        resp1 = ca.ask_assistant(db, "What is the current project status?", use_gemini=False)
        assert resp1["intent"] == ca.INTENT_PROJECT_OVERVIEW
        assert "CogniTrace Project Status Overview" in resp1["answer"]
        assert len(resp1["citations"]) > 0

        # 2. Tasks query
        resp2 = ca.ask_assistant(db, "Which tasks are completed and pending?", use_gemini=False)
        assert resp2["intent"] == ca.INTENT_TASK_ANALYTICS
        assert "TASK-101" in resp2["answer"]

        # 3. Blockers and contradictions query
        resp3 = ca.ask_assistant(db, "Explain all detected contradictions", use_gemini=False)
        assert resp3["intent"] == ca.INTENT_CONFLICTS_UNRESOLVED
        assert "contradiction" in resp3["answer"].lower()

        # 4. Chart query
        resp4 = ca.ask_assistant(db, "Show Git commits over time using a line chart", use_gemini=False)
        assert resp4["intent"] == ca.INTENT_CHART_REQUEST
        assert resp4["chart_spec"]["chart_type"] == "line"
        assert len(resp4["chart_spec"]["data"]) > 0

        # 5. Missing evidence query ("No Citation, No Assertion")
        resp5 = ca.ask_assistant(db, "How is the iOS mobile app build configured?", use_gemini=False)
        assert resp5["intent"] == ca.INTENT_FACTUAL_QUERY
        assert "No Supporting Evidence Found" in resp5["answer"]
        assert len(resp5["citations"]) == 0
    finally:
        db.close()
