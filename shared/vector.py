from __future__ import annotations

import hashlib
import math
import re
from typing import Iterable

from sqlalchemy import JSON
from sqlalchemy.types import TypeDecorator

try:  # Optional locally; required for real Supabase/Postgres pgvector columns.
    from pgvector.sqlalchemy import Vector as PgVector
except Exception:  # pragma: no cover - depends on local dependency installation.
    PgVector = None


EMBEDDING_DIMENSIONS = 1536
FALLBACK_EMBEDDING_MODEL = f"deterministic-hash-{EMBEDDING_DIMENSIONS}"


class EmbeddingVector(TypeDecorator):
    """Use pgvector on Postgres and JSON on SQLite/local test databases."""

    impl = JSON
    cache_ok = True

    def __init__(self, dimensions: int = EMBEDDING_DIMENSIONS):
        super().__init__()
        self.dimensions = dimensions

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql" and PgVector is not None:
            return dialect.type_descriptor(PgVector(self.dimensions))
        return dialect.type_descriptor(JSON())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return normalize_embedding(value, dimensions=self.dimensions)

    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return normalize_embedding(value, dimensions=self.dimensions)


def pgvector_python_available() -> bool:
    return PgVector is not None


def normalize_embedding(values: Iterable[float] | None, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float] | None:
    if values is None:
        return None
    vector = [float(value) for value in values]
    if len(vector) != dimensions:
        return None
    return vector


def deterministic_embedding(text: str, dimensions: int = EMBEDDING_DIMENSIONS) -> list[float]:
    """Small deterministic embedding fallback for offline demos and tests."""

    vector = [0.0] * dimensions
    tokens = re.findall(r"[A-Za-z0-9_]+|[\u4e00-\u9fff]", text.lower())
    if not tokens:
        tokens = [text or "empty"]

    for token in tokens:
        digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 else -1.0
        vector[index] += sign * (1.0 + (len(token) % 5) * 0.1)

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [round(value / norm, 8) for value in vector]


def embedding_for_text(text: str, client=None) -> tuple[list[float], str]:
    remote_embedding = None
    if client is not None and getattr(client, "available", False):
        remote_embedding = client.embed(text)

    normalised = normalize_embedding(remote_embedding)
    if normalised is not None:
        settings = getattr(client, "settings", None)
        model = getattr(settings, "openai_embedding_model", "text-embedding-3-small")
        return normalised, model
    return deterministic_embedding(text), FALLBACK_EMBEDDING_MODEL


def pgvector_literal(values: Iterable[float]) -> str:
    return "[" + ",".join(f"{float(value):.8f}" for value in values) + "]"


def vector_backend_name(bind) -> str:
    dialect_name = getattr(getattr(bind, "dialect", None), "name", "")
    if dialect_name == "postgresql" and pgvector_python_available():
        return "pgvector"
    return "json_fallback"
