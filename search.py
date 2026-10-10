import sys
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

DB_URL = "postgresql://app:app@localhost:5433/rag"
model = SentenceTransformer("all-MiniLM-L6-v2")

question = sys.argv[1]
q_emb = model.encode(question, normalize_embeddings=True)

with psycopg.connect(DB_URL) as conn:
    register_vector(conn)
    rows = conn.execute(
        "SELECT page, content, 1 - (embedding <=> %s) AS score "
        "FROM chunks ORDER BY embedding <=> %s LIMIT 5",
        (q_emb, q_emb),
    ).fetchall()

for page, content, score in rows:
    print(f"\n[page {page}] score={score:.3f}\n{content[:300]}...")