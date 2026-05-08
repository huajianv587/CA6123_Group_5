from integrations import OpenAIClient
from shared import models
from shared.database import init_db, session_scope
from shared.vector import embedding_for_text


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
                embedding, embedding_model = embedding_for_text(chunk, client)
                db.add(
                    models.KnowledgeChunk(
                        document_id=doc.id,
                        chunk_index=idx,
                        content=chunk,
                        embedding=embedding,
                        embedding_model=embedding_model,
                    )
                )


if __name__ == "__main__":
    rebuild_knowledge_index()
    print("Knowledge index rebuilt.")
