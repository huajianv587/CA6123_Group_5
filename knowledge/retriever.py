import math
from dataclasses import dataclass
from typing import Optional

from integrations import OpenAIClient
from knowledge.faq_store import FAQ_DOCUMENTS
from shared import models


@dataclass
class RetrievalResult:
    doc_id: str
    chunk_id: Optional[int]
    category: str
    source_title: str
    content: str
    score: float

    @property
    def question(self) -> str:
        return self.source_title

    @property
    def answer(self) -> str:
        return self.content

    def to_context_str(self) -> str:
        return f"[{self.source_title}] {self.content} (score={self.score:.2f})"


class KnowledgeRetriever:
    def __init__(self, store=None, score_threshold: float = 0.20, llm: Optional[OpenAIClient] = None):
        self.store = store
        self.score_threshold = score_threshold
        self.llm = llm or OpenAIClient()

    def build_index(self) -> None:
        return None

    def retrieve(self, query: str, top_k: int = 3, category: Optional[str] = None, category_filter: Optional[str] = None) -> list[RetrievalResult]:
        category = category or category_filter
        if self.store:
            results = self._db_retrieve(query, top_k=top_k, category=category)
            if results:
                return results
        return self._memory_retrieve(query, top_k=top_k, category=category)

    def _db_retrieve(self, query: str, top_k: int, category: Optional[str]) -> list[RetrievalResult]:
        docs_query = self.store.db.query(models.KnowledgeDocument)
        if category:
            docs_query = docs_query.filter(models.KnowledgeDocument.category == category)
        docs = docs_query.all()
        scored = []
        query_vec = self.llm.embed(query) if self.llm else None
        for doc in docs:
            chunk_rows = doc.chunks or []
            if query_vec and chunk_rows and any(chunk.embedding for chunk in chunk_rows):
                for chunk in chunk_rows:
                    score = self._cosine(query_vec, chunk.embedding or [])
                    scored.append((score, doc, chunk.content, chunk.id))
            else:
                haystack = f"{doc.title} {doc.content} {' '.join(doc.keywords or [])}"
                score = self._keyword_score(query, haystack, doc.keywords or [])
                scored.append((score, doc, doc.content, None))
        scored = [row for row in scored if row[0] >= self.score_threshold]
        scored.sort(key=lambda row: row[0], reverse=True)
        return [
            RetrievalResult(doc_id=doc.doc_id, chunk_id=chunk_id, category=doc.category, source_title=doc.title, content=content, score=score)
            for score, doc, content, chunk_id in scored[:top_k]
        ]

    def _memory_retrieve(self, query: str, top_k: int, category: Optional[str]) -> list[RetrievalResult]:
        scored = []
        for doc in FAQ_DOCUMENTS:
            if category and doc["category"] != category:
                continue
            haystack = f"{doc['question']} {doc['answer']} {' '.join(doc['keywords'])}"
            score = self._keyword_score(query, haystack, doc["keywords"])
            if score >= self.score_threshold:
                scored.append((score, doc))
        scored.sort(key=lambda row: row[0], reverse=True)
        return [
            RetrievalResult(doc_id=doc["id"], chunk_id=None, category=doc["category"], source_title=doc["question"], content=doc["answer"], score=score)
            for score, doc in scored[:top_k]
        ]

    def format_context(self, results: list[RetrievalResult], max_chars: int = 800) -> str:
        text = "\n".join(f"{i + 1}. {r.to_context_str()}" for i, r in enumerate(results))
        return text[:max_chars]

    def get_stats(self) -> dict:
        if not self.store:
            return {"source": "memory", "total_documents": len(FAQ_DOCUMENTS)}
        total = self.store.db.query(models.KnowledgeDocument).count()
        chunks = self.store.db.query(models.KnowledgeChunk).count()
        return {"source": "database", "total_documents": total, "total_chunks": chunks}

    def _keyword_score(self, query: str, text: str, keywords: list[str]) -> float:
        hits = sum(1 for kw in keywords if kw and kw in query)
        overlap = len(set(query) & set(text)) / max(len(set(query)), 1)
        return min(1.0, hits * 0.35 + overlap * 0.4)

    def _cosine(self, a: list[float], b: list[float]) -> float:
        if not a or not b or len(a) != len(b):
            return 0.0
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
