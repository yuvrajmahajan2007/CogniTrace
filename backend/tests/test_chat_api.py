"""
CogniTrace — Phase 3 Tests: Chatbot API Routes and Session Management
backend/tests/test_chat_api.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from datetime import datetime, timedelta
import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.api.chat import session_manager, ChatSessionManager
from app.core.config import settings

client = TestClient(app)


# ==============================================================================
# 1. VALID CHAT REQUEST & STRUCTURE
# ==============================================================================

def test_post_chat_message_valid():
    """Valid chat message returns 200 with structured grounded payload."""
    payload = {
        "session_id": "test_sess_001",
        "message": "What is the current project status?"
    }
    resp = client.post("/api/chat/message", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()

    assert data["session_id"] == "test_sess_001"
    assert "CogniTrace Project Status Overview" in data["answer"]
    assert data["intent"] == "project_overview"
    assert isinstance(data["citations"], list)
    assert len(data["citations"]) > 0
    assert isinstance(data["follow_up_suggestions"], list)
    assert len(data["follow_up_suggestions"]) > 0

    # Ensure GEMINI_API_KEY is never leaked
    raw_text = resp.text.lower()
    if settings.GEMINI_API_KEY:
        assert settings.GEMINI_API_KEY.lower() not in raw_text
    assert "gemini_api_key" not in raw_text


# ==============================================================================
# 2. VALIDATION & SECURITY
# ==============================================================================

def test_post_chat_message_empty_or_whitespace():
    """Empty or whitespace-only message must be rejected with 422."""
    # Empty string
    resp1 = client.post("/api/chat/message", json={"session_id": "sess_1", "message": ""})
    assert resp1.status_code == 422

    # Whitespace only
    resp2 = client.post("/api/chat/message", json={"session_id": "sess_1", "message": "   \n\t  "})
    assert resp2.status_code == 422


def test_post_chat_message_invalid_session_id():
    """Malicious or invalid session_id must be rejected with 400 or 422."""
    # Path traversal attempt
    resp1 = client.post("/api/chat/message", json={"session_id": "../../etc/passwd", "message": "hello"})
    assert resp1.status_code == 400

    # Empty session_id
    resp2 = client.post("/api/chat/message", json={"session_id": "   ", "message": "hello"})
    assert resp2.status_code == 422


def test_post_chat_message_length_limit():
    """Excessively long message exceeding 4000 characters must be rejected with 422."""
    long_msg = "A" * 4001
    resp = client.post("/api/chat/message", json={"session_id": "sess_1", "message": long_msg})
    assert resp.status_code == 422


# ==============================================================================
# 3. SESSION ISOLATION & FOLLOW-UPS
# ==============================================================================

def test_session_isolation():
    """Messages from different session_ids must remain strictly isolated."""
    sess_a = "session_iso_A"
    sess_b = "session_iso_B"

    # Clean sessions
    session_manager.clear_session(sess_a)
    session_manager.clear_session(sess_b)

    # Session A message
    r_a = client.post("/api/chat/message", json={"session_id": sess_a, "message": "Which tasks are completed and pending?"})
    assert r_a.status_code == 200

    # Session B message
    r_b = client.post("/api/chat/message", json={"session_id": sess_b, "message": "Summarise Git activity"})
    assert r_b.status_code == 200

    history_a = session_manager.get_history(sess_a)
    history_b = session_manager.get_history(sess_b)

    assert len(history_a) == 2
    assert len(history_b) == 2

    # Verify no content bleed between sessions
    assert history_a[0]["content"] == "Which tasks are completed and pending?"
    assert history_b[0]["content"] == "Summarise Git activity"


def test_follow_up_message_in_same_session():
    """Multi-turn conversation within the same session preserves context history."""
    sess_id = "session_follow_up"
    session_manager.clear_session(sess_id)

    # Turn 1
    r1 = client.post("/api/chat/message", json={"session_id": sess_id, "message": "What is the current project status?"})
    assert r1.status_code == 200

    # Turn 2 (follow-up)
    r2 = client.post("/api/chat/message", json={"session_id": sess_id, "message": "Explain all detected contradictions"})
    assert r2.status_code == 200

    history = session_manager.get_history(sess_id)
    assert len(history) == 4
    assert history[0]["role"] == "user"
    assert history[1]["role"] == "assistant"
    assert history[2]["role"] == "user"
    assert history[3]["role"] == "assistant"


# ==============================================================================
# 4. CITATION RESPONSE STRUCTURE
# ==============================================================================

def test_citation_structure_in_response():
    """Ensure every returned citation contains required audit fields."""
    resp = client.post(
        "/api/chat/message",
        json={"session_id": "cite_test", "message": "Which tasks are completed and pending?"}
    )
    assert resp.status_code == 200
    data = resp.json()
    citations = data.get("citations", [])
    assert len(citations) > 0

    for c in citations:
        assert "source_filename" in c and c["source_filename"]
        assert "excerpt" in c and c["excerpt"]
        assert c.get("chunk_id") is not None or c.get("claim_id") is not None


# ==============================================================================
# 5. CHART ENDPOINT & VALIDATION
# ==============================================================================

def test_get_analytics_chart_valid_datasets():
    """Test valid dataset queries for all supported types: bar, pie, line."""
    # 1. Task status (bar)
    r1 = client.get("/api/chat/analytics/chart?dataset=task_status&chart_type=bar")
    assert r1.status_code == 200
    d1 = r1.json()
    assert d1["chart_type"] == "bar"
    assert d1["title"] == "Task Status Distribution"
    assert len(d1["data"]) > 0

    # 2. Task priority (pie)
    r2 = client.get("/api/chat/analytics/chart?dataset=task_priority&chart_type=pie")
    assert r2.status_code == 200
    d2 = r2.json()
    assert d2["chart_type"] == "pie"
    assert d2["title"] == "Task Priority Distribution"

    # 3. Git commits (line)
    r3 = client.get("/api/chat/analytics/chart?dataset=git_commits&chart_type=line")
    assert r3.status_code == 200
    d3 = r3.json()
    assert d3["chart_type"] == "line"
    assert d3["title"] == "Git Commits Over Time"

    # 4. Conflicts (bar)
    r4 = client.get("/api/chat/analytics/chart?dataset=conflicts&chart_type=bar")
    assert r4.status_code == 200
    d4 = r4.json()
    assert d4["chart_type"] == "bar"


def test_get_analytics_chart_invalid_dataset():
    """Unsupported dataset names must be rejected with 400 Bad Request."""
    resp = client.get("/api/chat/analytics/chart?dataset=arbitrary_sql_injection")
    assert resp.status_code == 400
    assert "Unsupported dataset" in resp.json()["detail"]


def test_get_analytics_chart_invalid_chart_type():
    """Unsupported chart types must be rejected with 400 Bad Request."""
    resp = client.get("/api/chat/analytics/chart?dataset=task_status&chart_type=3d_donut")
    assert resp.status_code == 400
    assert "Unsupported chart_type" in resp.json()["detail"]


# ==============================================================================
# 6. SUGGESTIONS ENDPOINT
# ==============================================================================

def test_get_chat_suggestions():
    """GET /api/chat/suggestions returns curated categories and prompts."""
    resp = client.get("/api/chat/suggestions")
    assert resp.status_code == 200
    data = resp.json()
    suggestions = data.get("suggestions", [])
    assert len(suggestions) >= 6

    categories = {s["category"] for s in suggestions}
    assert "Project Overview" in categories
    assert "Visualizations" in categories
    assert "Task Breakdown" in categories


# ==============================================================================
# 7. SESSION EXPIRATION & CLEANUP BEHAVIOR
# ==============================================================================

def test_session_manager_expiration_and_turn_cap():
    """Verify session manager cleans up expired entries and caps maximum turns."""
    mgr = ChatSessionManager(ttl_seconds=10, max_turns=2)

    # Add active session
    mgr.add_turn("sess_active", "Hi", "Hello")
    assert mgr.get_session_count() == 1

    # Simulate expired session
    past_time = datetime.utcnow() - timedelta(seconds=20)
    mgr._sessions["sess_expired"] = {
        "history": [{"role": "user", "content": "Old"}],
        "created_at": past_time,
        "last_accessed": past_time
    }
    assert mgr.get_session_count() == 2

    # Cleanup should prune the expired one
    cleaned = mgr.cleanup_expired()
    assert cleaned == 1
    assert mgr.get_session_count() == 1
    assert "sess_active" in mgr._sessions

    # Test turn capping: max_turns=2 means max 4 messages
    mgr.add_turn("sess_active", "Msg 2", "Ans 2")
    mgr.add_turn("sess_active", "Msg 3", "Ans 3")
    history = mgr.get_history("sess_active")
    assert len(history) == 4
    assert history[0]["content"] == "Msg 2"
    assert history[-1]["content"] == "Ans 3"


def test_delete_chat_session_endpoint():
    """DELETE /api/chat/session/{session_id} resets conversation context."""
    sess_id = "session_to_delete"
    client.post("/api/chat/message", json={"session_id": sess_id, "message": "Hi"})
    assert len(session_manager.get_history(sess_id)) > 0

    del_resp = client.delete(f"/api/chat/session/{sess_id}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "cleared"
    assert len(session_manager.get_history(sess_id)) == 0


# ==============================================================================
# 8. EXISTING API REGRESSION TESTS
# ==============================================================================

def test_existing_api_regression():
    """Existing CogniTrace endpoints must remain operational and unaffected."""
    # Health
    r_health = client.get("/health")
    assert r_health.status_code == 200
    assert r_health.json() == {"status": "ok"}

    # Files
    r_files = client.get("/api/files")
    assert r_files.status_code == 200
    assert isinstance(r_files.json(), list)

    # Claims
    r_claims = client.get("/api/claims")
    assert r_claims.status_code == 200
    assert isinstance(r_claims.json(), list)

    # Reports
    r_reports = client.get("/api/reports")
    assert r_reports.status_code == 200
    assert isinstance(r_reports.json(), list)
