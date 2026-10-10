import sys
import ollama
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

DB_URL = "postgresql://app:app@localhost:5433/rag"
MODEL = "llama3.2:3b"   # change if you pulled a different model
TOP_K = 5

embedder = SentenceTransformer("all-MiniLM-L6-v2")

SYSTEM = (
    "You answer questions using ONLY the numbered context passages provided. "
    "Cite the page for every claim, like (p. 12). "
    "If the context does not contain the answer, reply exactly: "
    "'I could not find this in the document.' Do not use outside knowledge."
)


def retrieve(question: str, k: int = TOP_K):
    q_emb = embedder.encode(question, normalize_embeddings=True)
    with psycopg.connect(DB_URL) as conn:
        register_vector(conn)
        return conn.execute(
            "SELECT page, content FROM chunks ORDER BY embedding <=> %s LIMIT %s",
            (q_emb, k),
        ).fetchall()


def answer(question: str) -> str:
    chunks = retrieve(question)
    context = "\n\n".join(
        f"[{i}] (page {page}) {content}" for i, (page, content) in enumerate(chunks, 1)
    )
    resp = ollama.chat(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"},
        ],
        options={"temperature": 0, "num_ctx": 4096},
    )
    return resp["message"]["content"]


if __name__ == "__main__":
    print(answer(sys.argv[1]))