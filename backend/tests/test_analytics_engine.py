import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from datetime import datetime
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
from app.services import analytics_engine as ae


@pytest.fixture
def empty_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def populated_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    # 1. Uploaded files
    f_doc = UploadedFile(
        id=1, filename="handover.pdf", content_type="application/pdf",
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
    f_synth = UploadedFile(
        id=4, filename="synthetic_sample.csv", content_type="text/csv",
        size_bytes=512, status=ParsingStatus.completed, source_type="task"
    )
    session.add_all([f_doc, f_git, f_task, f_synth])
    session.flush()

    # 2. Evidence chunks
    ch1 = EvidenceChunk(
        id=1, file_id=1, chunk_index=0, text="System overview paragraph.",
        source_type="document", page_number=1
    )
    ch2 = EvidenceChunk(
        id=2, file_id=2, chunk_index=0,
        text="Git Commit 1a2b3c by Alice Dev <alice@example.com> on 2026-11-10 10:00:00: feat: Init auth [Changed files: auth.py, main.py]",
        source_type="git", record_id="1a2b3c", author="Alice Dev <alice@example.com>",
        record_timestamp="2026-11-10 10:00:00"
    )
    ch3 = EvidenceChunk(
        id=3, file_id=2, chunk_index=1,
        text="Git Commit 4d5e6f by Bob Smith <bob@example.com> on 2026-11-11 11:00:00: fix: Token refresh [Changed files: auth.py]",
        source_type="git", record_id="4d5e6f", author="Bob Smith <bob@example.com>",
        record_timestamp="2026-11-11 11:00:00"
    )
    ch4 = EvidenceChunk(
        id=4, file_id=3, chunk_index=0,
        text="Task TASK-101 [Completed]: Build login screen - Complete frontend form (Assignee: Alice Dev, Priority: High, Due: 2026-11-12)",
        source_type="task", record_id="TASK-101", author="Alice Dev",
        record_timestamp="2026-11-12"
    )
    ch5 = EvidenceChunk(
        id=5, file_id=3, chunk_index=1,
        text="Task TASK-102 [Open]: API Rate Limiting - Implement sliding window (Assignee: Bob Smith, Priority: Critical, Due: 2026-11-15)",
        source_type="task", record_id="TASK-102", author="Bob Smith",
        record_timestamp="2026-11-15"
    )
    ch6 = EvidenceChunk(
        id=6, file_id=4, chunk_index=0,
        text="Task TASK-999 [In Progress]: Demo synthetic test item (Assignee: Mock User, Priority: Low, Due: 2026-11-20)",
        source_type="task", record_id="TASK-999", author="Mock User",
        record_timestamp="2026-11-20"
    )
    session.add_all([ch1, ch2, ch3, ch4, ch5, ch6])
    session.flush()

    # 3. Claims
    c1 = Claim(
        id=1, claim_text="System overview paragraph.", claim_type=ClaimType.architecture_decision,
        status=ClaimStatus.approved, source_file_id=1, source_filename="handover.pdf"
    )
    c2 = Claim(
        id=2, claim_text="Login screen completed.", claim_type=ClaimType.completed_feature,
        status=ClaimStatus.approved, source_file_id=3, source_filename="tasks.csv"
    )
    c3 = Claim(
        id=3, claim_text="API Rate limiting is open.", claim_type=ClaimType.pending_feature,
        status=ClaimStatus.pending, source_file_id=3, source_filename="tasks.csv"
    )
    c4 = Claim(
        id=4, claim_text="Legacy note rejected.", claim_type=ClaimType.todo_fixme,
        status=ClaimStatus.rejected, source_file_id=2, source_filename="git_log.txt"
    )
    session.add_all([c1, c2, c3, c4])
    session.flush()

    # 4. Conflict flags
    cf1 = ConflictFlag(
        id=1, claim_a_id=2, claim_b_id=3, conflict_type="contradiction",
        description="Contradiction on rate limiter", resolved=False
    )
    cf2 = ConflictFlag(
        id=2, claim_a_id=1, claim_b_id=None, conflict_type="insufficient_evidence",
        description="Fragment needing context", resolved=False
    )
    session.add_all([cf1, cf2])
    session.commit()

    yield session
    session.close()


def test_empty_database_behaviour(empty_db):
    """Analytics must return clean empty structures without crashing on an empty DB."""
    tasks = ae.get_task_analytics(empty_db)
    assert tasks["total_tasks"] == 0
    assert tasks["by_status"] == []
    assert "No task records" in tasks["summary"]

    git = ae.get_git_analytics(empty_db)
    assert git["total_commits"] == 0
    assert git["by_date"] == []

    claims = ae.get_claims_analytics(empty_db)
    assert claims["total_claims"] == 0
    assert claims["by_review_status"] == []

    evidence = ae.get_evidence_analytics(empty_db)
    assert evidence["total_chunks"] == 0

    conflicts = ae.get_conflict_analytics(empty_db)
    assert conflicts["total_conflicts"] == 0

    timeline = ae.get_project_timeline(empty_db)
    assert timeline["total_events"] == 0


def test_task_status_and_priority_aggregation(populated_db):
    """Verify task breakdown by status, priority, and assignee."""
    tasks = ae.get_task_analytics(populated_db)
    assert tasks["total_tasks"] == 3
    assert tasks["unique_task_ids"] == 3

    statuses = {item["label"]: item["count"] for item in tasks["by_status"]}
    assert statuses.get("Completed") == 1
    assert statuses.get("Open") == 1
    assert statuses.get("In Progress") == 1

    priorities = {item["label"]: item["count"] for item in tasks["by_priority"]}
    assert priorities.get("High") == 1
    assert priorities.get("Critical") == 1
    assert priorities.get("Low") == 1

    assignees = {item["label"]: item["count"] for item in tasks["by_assignee"]}
    assert assignees.get("Alice Dev") == 1
    assert assignees.get("Bob Smith") == 1
    assert assignees.get("Mock User") == 1

    # Check synthetic identification
    synth_recs = [r for r in tasks["records"] if r["is_synthetic"]]
    assert len(synth_recs) == 1
    assert synth_recs[0]["task_id"] == "TASK-999"


def test_git_activity_aggregation(populated_db):
    """Verify commits by date, author, and changed files frequency."""
    git = ae.get_git_analytics(populated_db)
    assert git["total_commits"] == 2
    assert git["unique_commits"] == 2

    # Dates
    dates = {item["date"]: item["count"] for item in git["by_date"]}
    assert dates.get("2026-11-10") == 1
    assert dates.get("2026-11-11") == 1

    # Authors (cleaned without email)
    authors = {item["author"]: item["count"] for item in git["by_author"]}
    assert authors.get("Alice Dev") == 1
    assert authors.get("Bob Smith") == 1

    # Changed files frequency
    files_map = {item["file"]: item["frequency"] for item in git["changed_files"]}
    assert files_map.get("auth.py") == 2
    assert files_map.get("main.py") == 1


def test_claim_review_status_and_category_counts(populated_db):
    """Verify claim counts by approved/pending/rejected review status and claim category."""
    claims = ae.get_claims_analytics(populated_db)
    assert claims["total_claims"] == 4

    statuses = {item["status"]: item["count"] for item in claims["by_review_status"]}
    assert statuses.get("approved") == 2
    assert statuses.get("pending") == 1
    assert statuses.get("rejected") == 1

    categories = {item["category"]: item["count"] for item in claims["by_category"]}
    assert categories.get("architecture_decision") == 1
    assert categories.get("completed_feature") == 1
    assert categories.get("pending_feature") == 1
    assert categories.get("todo_fixme") == 1


def test_evidence_source_and_document_counts(populated_db):
    """Verify evidence chunks by source type and source document."""
    evidence = ae.get_evidence_analytics(populated_db)
    assert evidence["total_chunks"] == 6

    by_type = {item["source_type"]: item["count"] for item in evidence["by_source_type"]}
    assert by_type.get("task") == 3
    assert by_type.get("git") == 2
    assert by_type.get("document") == 1

    by_doc = {item["filename"]: item["chunk_count"] for item in evidence["by_document"]}
    assert by_doc.get("tasks.csv") == 2
    assert by_doc.get("git_log.txt") == 2
    assert by_doc.get("handover.pdf") == 1
    assert by_doc.get("synthetic_sample.csv") == 1


def test_conflict_analytics(populated_db):
    """Verify conflict counts by type, source document, and resolution status."""
    # Add a resolved flag to verify distinction
    resolved_flag = ConflictFlag(
        id=3, claim_a_id=2, claim_b_id=4, conflict_type="contradiction",
        description="Resolved task disagreement", resolved=True
    )
    populated_db.add(resolved_flag)
    populated_db.commit()

    conflicts = ae.get_conflict_analytics(populated_db)
    assert conflicts["total_conflicts"] == 3
    assert conflicts["unresolved_conflicts"] == 2
    assert conflicts["resolved_conflicts"] == 1

    by_res = {item["status"]: item["count"] for item in conflicts["by_resolution_status"]}
    assert by_res.get("unresolved") == 2
    assert by_res.get("resolved") == 1

    by_type = {item["type"]: item["count"] for item in conflicts["by_conflict_type"]}
    assert by_type.get("contradiction") == 2
    assert by_type.get("insufficient_evidence") == 1

    by_doc = {item["filename"]: item["count"] for item in conflicts["by_document"]}
    assert by_doc.get("tasks.csv") == 2
    assert by_doc.get("handover.pdf") == 1
    assert by_doc.get("git_log.txt") == 1


def test_timeline_ordering_and_event_types(populated_db):
    """Verify timeline merges file uploads, commits, and tasks chronologically while preserving source IDs and timestamps."""
    timeline = ae.get_project_timeline(populated_db, ascending=True)
    events = timeline["events"]
    assert len(events) >= 6

    event_types = {e["event_type"] for e in events}
    assert "document_upload" in event_types
    assert "git_commit" in event_types
    assert "task_milestone" in event_types

    # Verify source IDs and timestamps are preserved
    for ev in events:
        assert ev.get("source_id") is not None
        assert ev.get("record_id") is not None
        assert ev.get("event_type") in ("document_upload", "git_commit", "chat_message", "task_milestone")
        assert ev.get("original_timestamp") is not None

    # Chronological ordering check
    timestamps = [e["timestamp"] for e in events if e.get("timestamp")]
    assert timestamps == sorted(timestamps)


def test_duplicate_task_ids_across_multiple_imports_not_double_counted(empty_db):
    """
    Requirement 3: Verify duplicate task IDs across multiple imports are not incorrectly double-counted.
    Simulates importing sprint_1.csv with TASK-101 (Open), then sprint_2.csv with TASK-101 (Completed).
    """
    f1 = UploadedFile(id=1, filename="sprint_1.csv", content_type="text/csv", size_bytes=100, status=ParsingStatus.completed, source_type="task")
    f2 = UploadedFile(id=2, filename="sprint_2.csv", content_type="text/csv", size_bytes=100, status=ParsingStatus.completed, source_type="task")
    f3 = UploadedFile(id=3, filename="sprint_dup.csv", content_type="text/csv", size_bytes=100, status=ParsingStatus.completed, source_type="task")
    empty_db.add_all([f1, f2, f3])
    empty_db.flush()

    # Sprint 1 has TASK-101 Open
    ch1 = EvidenceChunk(id=1, file_id=1, chunk_index=0, text="Task TASK-101 [Open]: Payment flow (Assignee: Alice, Priority: High)", source_type="task", record_id="TASK-101", author="Alice")
    # Sprint 2 has TASK-101 Completed (superseding sprint 1)
    ch2 = EvidenceChunk(id=2, file_id=2, chunk_index=0, text="Task TASK-101 [Completed]: Payment flow (Assignee: Alice, Priority: High)", source_type="task", record_id="TASK-101", author="Alice")
    # Sprint dup has exact duplicate of Sprint 2
    ch3 = EvidenceChunk(id=3, file_id=3, chunk_index=0, text="Task TASK-101 [Completed]: Payment flow (Assignee: Alice, Priority: High)", source_type="task", record_id="TASK-101", author="Alice")
    # Sprint 2 also has TASK-102
    ch4 = EvidenceChunk(id=4, file_id=2, chunk_index=1, text="Task TASK-102 [Open]: User profile (Assignee: Bob, Priority: Medium)", source_type="task", record_id="TASK-102", author="Bob")
    empty_db.add_all([ch1, ch2, ch3, ch4])
    empty_db.commit()

    analytics = ae.get_task_analytics(empty_db, deduplicate=True)
    assert analytics["total_tasks"] == 2, f"Expected 2 unique tasks, got {analytics['total_tasks']}"
    assert analytics["total_chunks"] == 4, f"Expected 4 total chunks, got {analytics['total_chunks']}"
    assert analytics["duplicate_chunks_count"] == 2

    # Status breakdown must sum strictly to total_tasks (2)
    status_map = {item["label"]: item["count"] for item in analytics["by_status"]}
    assert status_map.get("Completed") == 1  # TASK-101 resolved to latest state (Completed)
    assert status_map.get("Open") == 1       # TASK-102
    assert sum(status_map.values()) == 2


def test_synthetic_data_labelling_no_false_positives(empty_db):
    """
    Requirement 7: Verify synthetic-data labelling does not misclassify genuine records
    even when document text contains the word 'sample'.
    """
    f_genuine = UploadedFile(
        id=1, filename="Architecture_Specification.pdf", content_type="application/pdf",
        size_bytes=4096, status=ParsingStatus.completed, source_type="document"
    )
    f_synth = UploadedFile(
        id=2, filename="synthetic_sample_data.csv", content_type="text/csv",
        size_bytes=512, status=ParsingStatus.completed, source_type="task"
    )
    empty_db.add_all([f_genuine, f_synth])
    empty_db.flush()

    # Genuine chunk containing words 'sample size' and 'sampling'
    ch_gen = EvidenceChunk(
        id=1, file_id=1, chunk_index=0,
        text="During architecture benchmarking, a sample size of 500 API calls demonstrated sub-50ms latency.",
        source_type="document"
    )
    # Synthetic chunk
    ch_synth = EvidenceChunk(
        id=2, file_id=2, chunk_index=0,
        text="Task TASK-101 [Open]: Synthetic mock task item (Assignee: Mock User, Priority: Low)",
        source_type="task", record_id="TASK-101"
    )
    empty_db.add_all([ch_gen, ch_synth])
    empty_db.commit()

    timeline = ae.get_project_timeline(empty_db)
    events = timeline["events"]

    gen_event = next(e for e in events if e["source_filename"] == "Architecture_Specification.pdf")
    synth_event = next(e for e in events if e["source_filename"] == "synthetic_sample_data.csv")

    assert gen_event["is_synthetic"] is False, "Genuine document was misclassified as synthetic!"
    assert synth_event["is_synthetic"] is True, "Synthetic file was not flagged as synthetic!"


def test_analytics_against_live_database():
    """Verify analytics engine against the actual live CogniTrace database."""
    db = SessionLocal()
    try:
        tasks = ae.get_task_analytics(db)
        assert tasks["total_tasks"] >= 1
        assert len(tasks["by_status"]) >= 1

        git = ae.get_git_analytics(db)
        assert git["total_commits"] >= 1
        assert len(git["by_author"]) >= 1

        claims = ae.get_claims_analytics(db)
        assert claims["total_claims"] >= 50
        assert any(item["status"] == "approved" for item in claims["by_review_status"])

        evidence = ae.get_evidence_analytics(db)
        assert evidence["total_chunks"] >= 20

        conflicts = ae.get_conflict_analytics(db)
        assert conflicts["total_conflicts"] == 5

        timeline = ae.get_project_timeline(db, limit=10)
        assert timeline["total_events"] >= 10
    finally:
        db.close()
