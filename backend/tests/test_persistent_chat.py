"""
CogniTrace — Persistent Chat History Tests
Tests for conversation CRUD APIs and persistence behavior.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.core.config import settings

client = TestClient(app)

CLIENT_ID = "test_persistent_client_001"


# ==============================================================================
# 1. CREATE CONVERSATION
# ==============================================================================

def test_create_conversation():
    """POST /api/chat/conversations creates a new conversation with valid client_id."""
    resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "Test Conversation"
    })
    assert resp.status_code == 201
    data = resp.json()
    assert data["client_id"] == CLIENT_ID
    assert data["title"] == "Test Conversation"
    assert "id" in data
    assert data["message_count"] == 0


# ==============================================================================
# 2. LIST CONVERSATIONS
# ==============================================================================

def test_list_conversations():
    """GET /api/chat/conversations returns conversations for the given client_id."""
    # Create a conversation first
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "List Test Conv"
    })
    assert create_resp.status_code == 201

    resp = client.get(f"/api/chat/conversations?client_id={CLIENT_ID}")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) >= 1
    titles = {c["title"] for c in data}
    assert "List Test Conv" in titles


# ==============================================================================
# 3. GET CONVERSATION DETAIL
# ==============================================================================

def test_get_conversation_detail():
    """GET /api/chat/conversations/{id} returns the conversation with messages."""
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "Detail Test Conv"
    })
    conv_id = create_resp.json()["id"]

    # Send a message in this conversation
    msg_resp = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "client_id": CLIENT_ID,
        "message": "What is the current project status?"
    })
    assert msg_resp.status_code == 200

    # Retrieve the conversation detail
    detail_resp = client.get(f"/api/chat/conversations/{conv_id}?client_id={CLIENT_ID}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["id"] == conv_id
    assert len(detail["messages"]) >= 2  # user + assistant


# ==============================================================================
# 4. UPDATE CONVERSATION TITLE
# ==============================================================================

def test_update_conversation_title():
    """PATCH /api/chat/conversations/{id} renames the conversation."""
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "Old Title"
    })
    conv_id = create_resp.json()["id"]

    patch_resp = client.patch(
        f"/api/chat/conversations/{conv_id}?client_id={CLIENT_ID}",
        json={"title": "Updated Title"}
    )
    assert patch_resp.status_code == 200
    assert patch_resp.json()["title"] == "Updated Title"


# ==============================================================================
# 5. DELETE CONVERSATION
# ==============================================================================

def test_delete_conversation():
    """DELETE /api/chat/conversations/{id} deletes conversation and messages."""
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "To Be Deleted"
    })
    conv_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/chat/conversations/{conv_id}?client_id={CLIENT_ID}")
    assert del_resp.status_code == 200
    assert del_resp.json()["status"] == "deleted"

    # Verify it's gone
    get_resp = client.get(f"/api/chat/conversations/{conv_id}?client_id={CLIENT_ID}")
    assert get_resp.status_code == 404


# ==============================================================================
# 6. CONVERSATION ISOLATION BY CLIENT ID
# ==============================================================================

def test_conversation_client_isolation():
    """Conversations from different client_ids must not be visible to each other."""
    client_a = "client_isolation_A"
    client_b = "client_isolation_B"

    client.post("/api/chat/conversations", json={"client_id": client_a, "title": "Conv A"})
    client.post("/api/chat/conversations", json={"client_id": client_b, "title": "Conv B"})

    # Client A should only see their own conversations
    resp_a = client.get(f"/api/chat/conversations?client_id={client_a}")
    assert resp_a.status_code == 200
    titles_a = {c["title"] for c in resp_a.json()}
    assert "Conv A" in titles_a
    assert "Conv B" not in titles_a


# ==============================================================================
# 7. MESSAGE PERSISTENCE ACROSS SESSIONS
# ==============================================================================

def test_message_persistence():
    """Messages are persisted in SQLite and survive re-fetching."""
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "Persistence Test"
    })
    conv_id = create_resp.json()["id"]

    # Send two messages
    client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "client_id": CLIENT_ID,
        "message": "Which tasks are completed?"
    })
    client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "client_id": CLIENT_ID,
        "message": "Show Git activity"
    })

    # Retrieve and verify persisted messages
    detail_resp = client.get(f"/api/chat/conversations/{conv_id}?client_id={CLIENT_ID}")
    assert detail_resp.status_code == 200
    msgs = detail_resp.json()["messages"]
    # Should have at least 4 messages: 2 user + 2 assistant
    assert len(msgs) >= 4
    user_msgs = [m for m in msgs if m["role"] == "user"]
    assert len(user_msgs) >= 2
    asst_msgs = [m for m in msgs if m["role"] == "assistant"]
    assert len(asst_msgs) >= 2


# ==============================================================================
# 8. CONVERSATION_ID IN MESSAGE RESPONSE
# ==============================================================================

def test_message_response_includes_conversation_id():
    """POST /api/chat/message response always includes conversation_id."""
    create_resp = client.post("/api/chat/conversations", json={
        "client_id": CLIENT_ID,
        "title": "Response Test"
    })
    conv_id = create_resp.json()["id"]

    msg_resp = client.post("/api/chat/message", json={
        "conversation_id": conv_id,
        "client_id": CLIENT_ID,
        "message": "What is the current project status?"
    })
    assert msg_resp.status_code == 200
    data = msg_resp.json()
    assert data["conversation_id"] == conv_id
    assert "session_id" in data  # backwards compatibility
