"""
CogniTrace — Test Configuration
Ensures the database tables (including conversations + chat_messages) are created
before any test that uses the TestClient or SessionLocal.
"""

import sys
from pathlib import Path

# Ensure `app` package is importable from the backend root
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.db import init_db  # noqa: E402


# Module-level init: run once when conftest is imported by pytest,
# which happens before any test collection / execution.
init_db()
