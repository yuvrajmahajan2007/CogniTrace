import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Base, Claim, ClaimType, ClaimStatus, ConflictFlag, UploadedFile, EvidenceChunk, Citation, ParsingStatus
from app.services.claim_extractor import _detect_conflicts, _is_insufficient_evidence


@pytest.fixture
def test_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()

    file_a = UploadedFile(
        id=1,
        filename="source_a.txt",
        content_type="text/plain",
        size_bytes=100,
        status=ParsingStatus.completed,
    )
    file_b = UploadedFile(
        id=2,
        filename="source_b.txt",
        content_type="text/plain",
        size_bytes=100,
        status=ParsingStatus.completed,
    )
    session.add_all([file_a, file_b])
    session.commit()

    yield session
    session.close()


def _add_claim(session, claim_id, text, claim_type, file_id, filename, record_id=None, source_type="document", insufficient=False):
    claim = Claim(
        id=claim_id,
        claim_text=text,
        claim_type=claim_type,
        status=ClaimStatus.pending,
        source_file_id=file_id,
        source_filename=filename,
        insufficient_evidence=insufficient,
    )
    chunk = EvidenceChunk(
        id=claim_id,
        file_id=file_id,
        chunk_index=claim_id,
        text=text,
        source_type=source_type,
        record_id=record_id,
    )
    citation = Citation(
        id=claim_id,
        claim_id=claim_id,
        evidence_chunk_id=chunk.id,
        filename=filename,
        excerpt=text,
    )
    session.add_all([claim, chunk, citation])
    session.commit()
    return claim


def test_different_task_ids_different_statuses_no_contradiction(test_db):
    """
    Requirement 1: Different task IDs (TASK-101 vs TASK-103) must not be flagged
    merely because their statuses differ (Completed vs In Progress).
    """
    _add_claim(
        test_db, 1,
        "Task TASK-101 [Completed]: Implement JWT authentication - Completed token verification",
        ClaimType.completed_feature, 1, "sprint_tasks.csv", record_id="TASK-101", source_type="task"
    )
    _add_claim(
        test_db, 2,
        "Task TASK-103 [In Progress]: Test production deployment - Staging tests ongoing",
        ClaimType.pending_feature, 2, "sprint_tasks_extra.json", record_id="TASK-103", source_type="task"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 0, f"Expected no contradictions for different task IDs, got: {contradictions}"


def test_same_task_id_completed_and_pending_contradiction(test_db):
    """
    Requirement 2 & 4: Same task ID (TASK-101) reported as Completed in one source
    and Pending/Open in another is a confirmed status contradiction.
    """
    _add_claim(
        test_db, 1,
        "Task TASK-101 [Completed]: Implement JWT authentication - Token verification verified",
        ClaimType.completed_feature, 1, "sprint_a.csv", record_id="TASK-101", source_type="task"
    )
    _add_claim(
        test_db, 2,
        "Task TASK-101 [Pending]: Implement JWT authentication - Still pending security review",
        ClaimType.pending_feature, 2, "sprint_b.json", record_id="TASK-101", source_type="task"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 1
    assert "TASK-101" in contradictions[0].description
    assert contradictions[0].claim_a_id in (1, 2)
    assert contradictions[0].claim_b_id in (1, 2)


def test_same_postgres_migration_pending_in_two_sources_no_contradiction(test_db):
    """
    Requirement 3: Agreement detection. Two sources reporting the same pending status
    for PostgreSQL migration must not produce a contradiction.
    """
    _add_claim(
        test_db, 1,
        "Chat (Rohan Verma at 2026-11-11 09:30:00): The PostgreSQL migration script is still pending.",
        ClaimType.pending_feature, 1, "sample_chat_export.json", record_id="msg-102", source_type="chat"
    )
    _add_claim(
        test_db, 2,
        "Task TASK-102 [Pending]: Create PostgreSQL migration script - Prepare schema migration scripts",
        ClaimType.pending_feature, 2, "sample_task_records.csv", record_id="TASK-102", source_type="task"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 0, f"Expected no contradictions for agreement on pending migration, got: {contradictions}"


def test_jwt_auth_completion_and_postgres_migration_todo_no_contradiction(test_db):
    """
    Requirement 2: Different Git commits and different activities (JWT auth vs PostgreSQL TODO)
    must not automatically create conflicts.
    """
    _add_claim(
        test_db, 1,
        "Git Commit a1b2c3d4e5f6 by Priya Sharma <priya@example.com> on 2026-11-10 14:30:00: feat: Implemented JWT authentication middleware for API routes [Changed files: backend/app/auth.py]",
        ClaimType.completed_feature, 1, "git_history.txt", record_id="a1b2c3d4e5f6", source_type="git"
    )
    _add_claim(
        test_db, 2,
        "Git Commit f6e5d4c3b2a1 by Rohan Verma <rohan@example.com> on 2026-11-11 09:15:00: TODO: Add PostgreSQL migration script before production release [Changed files: backend/app/db/migrations.py]",
        ClaimType.todo_fixme, 2, "git_history.txt", record_id="f6e5d4c3b2a1", source_type="git"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 0, f"Expected no contradictions between unrelated Git commits, got: {contradictions}"


def test_problem_statement_and_solution_no_contradiction(test_db):
    """
    Requirement 5: Do not flag related problem statements and proposed solutions as contradictions.
    """
    _add_claim(
        test_db, 1,
        "Applying generic LLM summarizers introduces dangerous hallucinations, invents missing facts, and leaks confidential credentials.",
        ClaimType.blocker_risk, 1, "spec_doc.pdf"
    )
    _add_claim(
        test_db, 2,
        "CogniTrace strictly enforces the 'No Citation, No Assertion' Rule: The LLM is strictly constrained from producing any statement without verified reference links.",
        ClaimType.completed_feature, 1, "spec_doc.pdf"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 0, f"Expected no contradictions between problem statement and solution, got: {contradictions}"


def test_incomplete_evidence_fragment_insufficient_evidence_warning(test_db):
    """
    Requirement 7: Keep insufficient-evidence detection for incomplete or ambiguous fragments.
    """
    fragment = "missing personal notes."
    assert _is_insufficient_evidence(fragment) is True

    _add_claim(
        test_db, 1,
        fragment,
        ClaimType.pending_feature, 1, "notes.pdf", insufficient=True
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    insufficient_flags = [f for f in flags if f.conflict_type == "insufficient_evidence"]
    assert len(insufficient_flags) == 1
    assert "brief or ambiguous wording" in insufficient_flags[0].description


def test_cross_source_genuine_contradiction_billing_webhook(test_db):
    """
    Requirement 4: Detect genuine cross-source contradictions when sources refer
    to the same identifiable feature and explicitly report incompatible statuses.
    """
    _add_claim(
        test_db, 1,
        "Chat (Ananya at 2026-11-11 16:00): The billing webhook handler is completed and verified in staging.",
        ClaimType.completed_feature, 1, "team_chat.txt", source_type="chat"
    )
    _add_claim(
        test_db, 2,
        "Task TASK-101 [open]: Billing webhook handler - Complete Stripe webhook signature verification (Assignee: Ananya, Priority: high, Due: 2026-11-20)",
        ClaimType.pending_feature, 2, "sprint_tasks.csv", record_id="TASK-101", source_type="task"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    contradictions = [f for f in flags if f.conflict_type == "contradiction"]
    assert len(contradictions) == 1
    assert "billing, handler, webhook" in contradictions[0].description


def test_moderate_divergence_review_warning(test_db):
    """
    Requirement 8: Where the system cannot confidently determine whether two claims
    contradict each other, use a review warning rather than declaring a confirmed contradiction.
    """
    _add_claim(
        test_db, 1,
        "The notification dispatch pipeline is completed and active in production.",
        ClaimType.completed_feature, 1, "release_notes.txt"
    )
    _add_claim(
        test_db, 2,
        "The notification dispatch pipeline fallback queue is pending additional load testing and benchmark validation.",
        ClaimType.pending_feature, 2, "backlog_notes.txt"
    )

    new_flags = _detect_conflicts(test_db)
    flags = test_db.query(ConflictFlag).all()

    warnings = [f for f in flags if f.conflict_type == "review_warning"]
    assert len(warnings) == 1
    assert "Review warning" in warnings[0].description
    assert "notification, pipeline" in warnings[0].description


if __name__ == "__main__":
    pytest.main(["-v", __file__])
