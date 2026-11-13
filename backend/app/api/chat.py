"""
CogniTrace — Phase 3 & Part B: Chatbot API Routes and Persistent Session Management
backend/app/api/chat.py
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import threading
import logging
import json
import uuid
import re

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from ..db import SessionLocal
from ..models import Conversation, ChatMessage
from ..schemas.chat import (
    ChatMessageRequest,
    ChatMessageResponse,
    ChatSuggestionsResponse,
    ChatSuggestionItem,
    ChartSpecSchema,
    ChatCitationSchema,
    ConversationSummarySchema,
    ConversationDetailSchema,
    StoredChatMessageSchema,
    CreateConversationRequest,
    UpdateConversationRequest,
)
from ..services import chat_assistant as ca

logger = logging.getLogger(__name__)

router = APIRouter()

# Dependency to provide SQLAlchemy DB session
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# ==============================================================================
# IN-MEMORY SESSION MANAGER (BACKWARDS COMPATIBILITY & ACTIVE CACHE)
# ==============================================================================

class ChatSessionManager:
    """
    Thread-safe in-memory session manager maintained for backward compatibility.
    Primary persistence is stored in SQLite (Conversation and ChatMessage tables).
    """
    def __init__(self, ttl_seconds: int = 7200, max_turns: int = 30):
        self.ttl_seconds = ttl_seconds
        self.max_turns = max_turns
        self._sessions: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_history(self, session_id: str) -> List[Dict[str, str]]:
        with self._lock:
            self._cleanup_expired_locked()
            session = self._sessions.get(session_id)
            if not session:
                return []
            session["last_accessed"] = datetime.utcnow()
            return list(session["history"])

    def add_turn(self, session_id: str, user_msg: str, assistant_msg: str) -> None:
        with self._lock:
            self._cleanup_expired_locked()
            now = datetime.utcnow()
            if session_id not in self._sessions:
                self._sessions[session_id] = {
                    "history": [],
                    "created_at": now,
                    "last_accessed": now
                }
            session = self._sessions[session_id]
            session["last_accessed"] = now
            session["history"].append({"role": "user", "content": user_msg})
            session["history"].append({"role": "assistant", "content": assistant_msg})

            max_entries = self.max_turns * 2
            if len(session["history"]) > max_entries:
                session["history"] = session["history"][-max_entries:]

    def clear_session(self, session_id: str) -> bool:
        with self._lock:
            if session_id in self._sessions:
                del self._sessions[session_id]
                return True
            return False

    def cleanup_expired(self, now: Optional[datetime] = None) -> int:
        with self._lock:
            return self._cleanup_expired_locked(now)

    def _cleanup_expired_locked(self, now: Optional[datetime] = None) -> int:
        if now is None:
            now = datetime.utcnow()
        cutoff = now - timedelta(seconds=self.ttl_seconds)
        expired_keys = [
            sid for sid, data in self._sessions.items()
            if data["last_accessed"] < cutoff
        ]
        for sid in expired_keys:
            del self._sessions[sid]
        return len(expired_keys)

    def get_session_count(self) -> int:
        with self._lock:
            return len(self._sessions)


# Global session manager instance
session_manager = ChatSessionManager(ttl_seconds=7200, max_turns=30)


# ==============================================================================
# ALLOWED ANALYTICS DATASETS & CHART TYPES
# ==============================================================================

ALLOWED_DATASETS = {
    "task_status",
    "task_priority",
    "task_assignee",
    "git_commits",
    "claims_category",
    "evidence_sources",
    "conflicts",
}

ALLOWED_CHART_TYPES = {
    "bar",
    "pie",
    "line",
    "timeline",
}


# ==============================================================================
# PERSISTENT CONVERSATION CRUD APIS (PART B)
# ==============================================================================

@router.get(
    "/conversations",
    response_model=List[ConversationSummarySchema],
    summary="List all conversations for a client browser",
)
def list_conversations(
    client_id: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db)
):
    """
    Retrieves all persistent conversations owned by the specified client_id,
    ordered by most recently updated.
    """
    convs = (
        db.query(Conversation)
        .filter(Conversation.client_id == client_id)
        .order_by(Conversation.updated_at.desc())
        .all()
    )
    summaries = []
    for c in convs:
        count = db.query(ChatMessage).filter(ChatMessage.conversation_id == c.id).count()
        summaries.append(
            ConversationSummarySchema(
                id=c.id,
                client_id=c.client_id,
                title=c.title,
                created_at=c.created_at,
                updated_at=c.updated_at,
                message_count=count
            )
        )
    return summaries


@router.post(
    "/conversations",
    response_model=ConversationSummarySchema,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation for a client browser",
)
def create_conversation(
    payload: CreateConversationRequest,
    db: Session = Depends(get_db)
):
    """
    Creates a new persistent conversation for client_id.
    """
    conv_id = f"conv_{int(datetime.utcnow().timestamp())}_{uuid.uuid4().hex[:8]}"
    title = (payload.title or "New Conversation").strip()
    conv = Conversation(
        id=conv_id,
        client_id=payload.client_id,
        title=title,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(conv)
    db.commit()
    db.refresh(conv)

    return ConversationSummarySchema(
        id=conv.id,
        client_id=conv.client_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=0
    )


@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailSchema,
    summary="Get complete persistent message history for a conversation",
)
def get_conversation_detail(
    conversation_id: str,
    client_id: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db)
):
    """
    Retrieves a conversation and all its historical messages.
    Validates client_id ownership to prevent cross-client leaks.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )

    # Allow access if client matches or if legacy default_client
    if conv.client_id != client_id and conv.client_id != "default_client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation."
        )

    msgs = (
        db.query(ChatMessage)
        .filter(ChatMessage.conversation_id == conversation_id)
        .order_by(ChatMessage.created_at.asc())
        .all()
    )

    formatted_msgs = []
    for m in msgs:
        cites = []
        if m.citations_json:
            try:
                cites = [ChatCitationSchema(**c) for c in json.loads(m.citations_json)]
            except Exception:
                cites = []

        chart_spec = None
        if m.chart_spec_json:
            try:
                chart_spec = ChartSpecSchema(**json.loads(m.chart_spec_json))
            except Exception:
                chart_spec = None

        follow_ups = []
        if m.follow_ups_json:
            try:
                follow_ups = json.loads(m.follow_ups_json)
            except Exception:
                follow_ups = []

        formatted_msgs.append(
            StoredChatMessageSchema(
                id=m.id,
                conversation_id=m.conversation_id,
                role=m.role,
                content=m.content,
                intent=m.intent,
                citations=cites,
                chart_spec=chart_spec,
                follow_up_suggestions=follow_ups,
                created_at=m.created_at
            )
        )

    return ConversationDetailSchema(
        id=conv.id,
        client_id=conv.client_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        messages=formatted_msgs
    )


@router.patch(
    "/conversations/{conversation_id}",
    response_model=ConversationSummarySchema,
    summary="Update conversation title",
)
def update_conversation(
    conversation_id: str,
    payload: UpdateConversationRequest,
    client_id: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db)
):
    """
    Renames a conversation.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    if conv.client_id != client_id and conv.client_id != "default_client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation."
        )

    conv.title = payload.title.strip()
    conv.updated_at = datetime.utcnow()
    db.commit()
    db.refresh(conv)

    count = db.query(ChatMessage).filter(ChatMessage.conversation_id == conv.id).count()
    return ConversationSummarySchema(
        id=conv.id,
        client_id=conv.client_id,
        title=conv.title,
        created_at=conv.created_at,
        updated_at=conv.updated_at,
        message_count=count
    )


@router.delete(
    "/conversations/{conversation_id}",
    summary="Delete conversation and all its messages",
    status_code=status.HTTP_200_OK,
)
def delete_conversation(
    conversation_id: str,
    client_id: str = Query(..., min_length=1, max_length=128),
    db: Session = Depends(get_db)
):
    """
    Deletes conversation and cascades deletion to all messages in SQLite.
    """
    conv = db.query(Conversation).filter(Conversation.id == conversation_id).first()
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Conversation '{conversation_id}' not found."
        )
    if conv.client_id != client_id and conv.client_id != "default_client":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You do not have access to this conversation."
        )

    db.delete(conv)
    db.commit()

    # Also clean up in-memory session if cached
    session_manager.clear_session(conversation_id)

    return {
        "status": "deleted",
        "conversation_id": conversation_id
    }


# ==============================================================================
# CHAT MESSAGE PROCESSING WITH SQLITE PERSISTENCE
# ==============================================================================

@router.post(
    "/message",
    response_model=ChatMessageResponse,
    summary="Process conversational message with evidence grounding & SQLite persistence",
    status_code=status.HTTP_200_OK,
)
def send_chat_message(
    payload: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Accepts a user question, session_id/conversation_id, and client_id.
    - Validates message input and session id.
    - Persists user message into SQLite.
    - Retrieves conversational context from SQLite.
    - Invokes chat_assistant for evidence grounding, citations, and optional chart spec.
    - Persists assistant response and citation metadata into SQLite.
    - Updates conversation title on first turn.
    - Returns structured answer, citations, intent, chart specification, and follow-up suggestions.
    """
    conv_id = payload.conversation_id or payload.session_id
    if not conv_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Either conversation_id or session_id must be provided."
        )

    # Sanitize identifier to reject path traversal or malicious input
    if not re.match(r"^[A-Za-z0-9_\-\.]{1,128}$", conv_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid conversation_id format. Must be 1-128 alphanumeric characters, dashes, dots, or underscores."
        )

    client_id = payload.client_id or "default_client"
    if not re.match(r"^[A-Za-z0-9_\-\.]{1,128}$", client_id):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid client_id format."
        )

    try:
        # 1. Retrieve or auto-create conversation in SQLite
        conv = db.query(Conversation).filter(Conversation.id == conv_id).first()
        if conv:
            if conv.client_id != "default_client" and payload.client_id and conv.client_id != payload.client_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="You do not have access to this conversation."
                )
        else:
            first_line = payload.message.split("\n")[0].strip()
            title = (first_line[:40] + "...") if len(first_line) > 40 else first_line
            conv = Conversation(
                id=conv_id,
                client_id=client_id,
                title=title or "New Conversation",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow()
            )
            db.add(conv)
            db.commit()
            db.refresh(conv)

        # Auto-update title from first message if default
        if conv.title in ["New Conversation", "New Chat"]:
            first_line = payload.message.split("\n")[0].strip()
            conv.title = (first_line[:40] + "...") if len(first_line) > 40 else first_line

        # 2. Persist user message to SQLite
        user_msg_row = ChatMessage(
            conversation_id=conv_id,
            role="user",
            content=payload.message,
            created_at=datetime.utcnow()
        )
        db.add(user_msg_row)
        db.commit()

        # 3. Retrieve recent context history from SQLite
        past_msgs = (
            db.query(ChatMessage)
            .filter(ChatMessage.conversation_id == conv_id)
            .order_by(ChatMessage.created_at.asc())
            .all()
        )
        history = [{"role": m.role, "content": m.content} for m in past_msgs[-20:]]

        # 4. Invoke evidence-grounded chat assistant
        resp = ca.ask_assistant(
            db=db,
            query=payload.message,
            conversation_history=history,
            use_gemini=True
        )

        # 5. Persist assistant response to SQLite
        citations = resp.get("citations", [])
        chart_spec = resp.get("chart_spec")
        follow_ups = resp.get("follow_up_suggestions", [])

        asst_msg_row = ChatMessage(
            conversation_id=conv_id,
            role="assistant",
            content=resp.get("answer", ""),
            intent=resp.get("intent", "factual_query"),
            citations_json=json.dumps(citations) if citations else None,
            chart_spec_json=json.dumps(chart_spec) if chart_spec else None,
            follow_ups_json=json.dumps(follow_ups) if follow_ups else None,
            created_at=datetime.utcnow()
        )
        db.add(asst_msg_row)
        conv.updated_at = datetime.utcnow()
        db.commit()

        # Update in-memory session cache for legacy compatibility
        session_manager.add_turn(
            session_id=conv_id,
            user_msg=payload.message,
            assistant_msg=resp.get("answer", "")
        )

        chart_spec_data = None
        if chart_spec:
            chart_spec_data = ChartSpecSchema(**chart_spec)

        return ChatMessageResponse(
            conversation_id=conv_id,
            session_id=conv_id,
            answer=resp.get("answer", ""),
            intent=resp.get("intent", "factual_query"),
            citations=citations,
            chart_spec=chart_spec_data,
            analytics_payload=resp.get("analytics_payload"),
            follow_up_suggestions=follow_ups
        )

    except HTTPException:
        raise
    except Exception as exc:
        logger.error("Chat message processing failed: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while generating the conversational response."
        )


@router.get(
    "/suggestions",
    response_model=ChatSuggestionsResponse,
    summary="Get recommended example questions based on evidence and analytics",
)
def get_chat_suggestions():
    """
    Returns curated, relevant example questions spanning project status, tasks,
    git history, conflict resolution, and dynamic visualizations.
    """
    suggestions = [
        ChatSuggestionItem(
            category="Approved Claims",
            prompt="Show all approved claims.",
            description="Retrieve and display all human-verified approved claims with source citations.",
            target_intent="approved_claims"
        ),
        ChatSuggestionItem(
            category="Task Comparison",
            prompt="Identify all duplicate task IDs with different descriptions.",
            description="Compare task records across sources, detect collisions vs genuine contradictions.",
            target_intent="task_comparison"
        ),
        ChatSuggestionItem(
            category="Task Listing",
            prompt="List all unique tasks with task IDs, descriptions, statuses, assignees and source filenames.",
            description="Reconciled unique task records with full provenance.",
            target_intent="task_listing"
        ),
        ChatSuggestionItem(
            category="Team Chat Summary",
            prompt="Summarize all imported team chat messages. Show the speaker, timestamp, message, and source filename. Separate decisions, completed work, pending work, and contradictions.",
            description="Complete team chat analysis categorized by decisions, work status, and discrepancies.",
            target_intent="chat_summary"
        ),
        ChatSuggestionItem(
            category="Task Breakdown",
            prompt="Which tasks are completed and pending?",
            description="Deduplicated task records with statuses and assignees from all sources.",
            target_intent="task_analytics"
        ),
        ChatSuggestionItem(
            category="Project Overview",
            prompt="What is the current project status?",
            description="High-level health check, tasks, git activity, and knowledge claims overview.",
            target_intent="project_overview"
        ),
        ChatSuggestionItem(
            category="Visualizations",
            prompt="Show completed vs pending tasks in a bar graph",
            description="Dynamic bar chart comparing completed vs open project tasks.",
            target_intent="chart_request"
        ),
        ChatSuggestionItem(
            category="Visualizations",
            prompt="Generate a pie chart of task priority distribution",
            description="Dynamic pie chart showing Critical, High, Medium, and Low tasks.",
            target_intent="chart_request"
        ),
        ChatSuggestionItem(
            category="Git Activity",
            prompt="Show Git commits over time using a line chart",
            description="Chronological line chart showing commit velocity over time.",
            target_intent="chart_request"
        ),
        ChatSuggestionItem(
            category="Blockers & Contradictions",
            prompt="Explain all detected contradictions",
            description="Examine flagged discrepancies between tasks, chats, and documentation.",
            target_intent="conflicts_unresolved"
        ),
    ]
    return ChatSuggestionsResponse(suggestions=suggestions)


@router.get(
    "/analytics/chart",
    response_model=ChartSpecSchema,
    summary="Get validated chart specification for predefined analytics datasets",
)
def get_analytics_chart(
    dataset: str = Query(..., description="Analytics dataset: task_status, task_priority, task_assignee, git_commits, claims_category, evidence_sources, conflicts"),
    chart_type: Optional[str] = Query(None, description="Preferred chart type: bar, pie, line, timeline"),
    db: Session = Depends(get_db)
):
    """
    Returns a declarative chart specification strictly from predefined analytics datasets.
    - Validates dataset and chart_type against allowed sets.
    - Never accepts or executes arbitrary SQL or dynamic code.
    """
    clean_dataset = dataset.strip().lower()
    if clean_dataset not in ALLOWED_DATASETS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported dataset '{dataset}'. Supported datasets: {', '.join(sorted(ALLOWED_DATASETS))}."
        )

    clean_chart_type = (chart_type.strip().lower() if chart_type else "bar")
    if clean_chart_type not in ALLOWED_CHART_TYPES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported chart_type '{chart_type}'. Supported chart types: {', '.join(sorted(ALLOWED_CHART_TYPES))}."
        )

    try:
        spec, desc = ca.generate_chart_spec(clean_dataset, clean_chart_type, db)
        spec["description"] = desc
        return ChartSpecSchema(**spec)
    except Exception as exc:
        logger.error("Failed to generate chart specification for %s: %s", dataset, exc, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate the requested chart specification."
        )


@router.delete(
    "/session/{session_id}",
    summary="Clear in-memory conversational history for a session (Legacy)",
    status_code=status.HTTP_200_OK,
)
def clear_chat_session(session_id: str, db: Session = Depends(get_db)):
    """
    Clears conversation history for the specified session_id / conversation_id.
    """
    # Clear in DB if exists
    conv = db.query(Conversation).filter(Conversation.id == session_id).first()
    if conv:
        db.delete(conv)
        db.commit()

    cleared = session_manager.clear_session(session_id)
    return {
        "status": "cleared" if (cleared or conv) else "not_found",
        "session_id": session_id
    }
