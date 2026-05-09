from contextlib import contextmanager

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from shared.config import get_settings
from shared.vector import pgvector_python_available


class Base(DeclarativeBase):
    pass


def _normalize_database_url(url: str) -> str:
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    return url


settings = get_settings()
_db_url = _normalize_database_url(settings.database_url)
_is_sqlite = _db_url.startswith("sqlite")
engine = create_engine(
    _db_url,
    pool_pre_ping=True,
    **({"connect_args": {"check_same_thread": False, "timeout": 20}} if _is_sqlite else {}),
)
if _is_sqlite:
    # WAL mode: allows concurrent reads while a write is in progress
    with engine.begin() as _conn:
        _conn.execute(text("PRAGMA journal_mode=WAL"))
        _conn.execute(text("PRAGMA busy_timeout=10000"))
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)


def init_db() -> None:
    from shared import models  # noqa: F401

    if engine.dialect.name == "postgresql":
        with engine.begin() as conn:
            conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            _drop_legacy_json_chunk_index(conn)
    Base.metadata.create_all(bind=engine)
    _create_vector_indexes()


def _drop_legacy_json_chunk_index(conn) -> None:
    if not pgvector_python_available():
        return
    column_type = conn.execute(
        text(
            """
            SELECT udt_name
            FROM information_schema.columns
            WHERE table_name = 'knowledge_chunks' AND column_name = 'embedding'
            """
        )
    ).scalar()
    if column_type and column_type != "vector":
        # knowledge_chunks is a derived RAG index table and can be rebuilt from knowledge_documents.
        conn.execute(text("DROP TABLE IF EXISTS knowledge_chunks CASCADE"))


def _create_vector_indexes() -> None:
    if engine.dialect.name != "postgresql" or not pgvector_python_available():
        return
    try:
        with engine.begin() as conn:
            conn.execute(text("ALTER TABLE knowledge_chunks ADD COLUMN IF NOT EXISTS embedding_model VARCHAR(120)"))
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_chunks_embedding_hnsw "
                    "ON knowledge_chunks USING hnsw (embedding vector_cosine_ops)"
                )
            )
            conn.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS ix_knowledge_documents_category "
                    "ON knowledge_documents (category)"
                )
            )
    except SQLAlchemyError:
        # Existing demo databases may still have the old JSON embedding column.
        # Keep startup usable; verify_supabase.py reports the actual column type.
        return


@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def get_db():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
