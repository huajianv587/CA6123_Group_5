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
engine = create_engine(_normalize_database_url(settings.database_url), pool_pre_ping=True)
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
