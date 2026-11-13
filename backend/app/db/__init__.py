import os
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base
from ..core.config import settings

DATABASE_URL = settings.SQLITE_DB_PATH

# Ensure parent directory exists for file-backed SQLite paths (e.g. /data/cognitrace.db)
if DATABASE_URL.startswith("sqlite:///"):
    db_file_path = DATABASE_URL.replace("sqlite:///", "", 1)
    db_parent = os.path.dirname(db_file_path)
    if db_parent:
        os.makedirs(db_parent, exist_ok=True)

engine = create_engine(
    DATABASE_URL, connect_args={"check_same_thread": False}
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def _add_missing_columns(table_name: str, columns: dict) -> None:
    """Additive, idempotent SQLite column migration without dropping/recreating tables."""
    with engine.begin() as conn:
        existing = {
            row[1]
            for row in conn.execute(text(f"PRAGMA table_info({table_name})")).fetchall()
        }
        for col_name, col_def in columns.items():
            if col_name not in existing:
                conn.execute(text(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_def}"))


def init_db():
    # Import models so that they are registered with Base.metadata
    # Models live in app.models (NOT app.db.models)
    from app import models  # noqa: F401
    Base.metadata.create_all(bind=engine)

    # Additive migrations for existing SQLite tables
    _add_missing_columns(
        "uploaded_files",
        {
            "source_type": "VARCHAR NOT NULL DEFAULT 'document'",
            "file_hash": "VARCHAR",
            "records_count": "INTEGER NOT NULL DEFAULT 0",
        },
    )
    _add_missing_columns(
        "evidence_chunks",
        {
            "source_type": "VARCHAR NOT NULL DEFAULT 'document'",
            "record_id": "VARCHAR",
            "record_fingerprint": "VARCHAR",
            "author": "VARCHAR",
            "record_timestamp": "VARCHAR",
        },
    )


# Automatically initialize DB tables upon import
try:
    init_db()
except Exception:
    pass
