from integrations import OpenAIClient
from shared import models
from shared.database import init_db, session_scope


def chunk_text(text: str, size: int = 420, overlap: int = 60) -> list[str]:
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + size])
        start += max(size - overlap, 1)
    return chunks or [text]


def rebuild_knowledge_index() -> None:
    init_db()
    client = OpenAIClient()
    with session_scope() as db:
        db.query(models.KnowledgeChunk).delete()
        docs = db.query(models.KnowledgeDocument).all()
        for doc in docs:
            for idx, chunk in enumerate(chunk_text(doc.content)):
                embedding = client.embed(chunk) if client.available else None
                db.add(models.KnowledgeChunk(document_id=doc.id, chunk_index=idx, content=chunk, embedding=embedding))


if __name__ == "__main__":
    rebuild_knowledge_index()
    print("Knowledge index rebuilt.")
