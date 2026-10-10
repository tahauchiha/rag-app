import re
import sys
import pathlib
import fitz  # PyMuPDF
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer

DB_URL = "postgresql://app:app@localhost:5433/rag"
MIN_CHUNK = 150  # drop tiny chunks such as figure captions
model = SentenceTransformer("all-MiniLM-L6-v2")


def clean(text: str) -> str:
    text = re.sub(r"\.{3,}", " ", text)  # dot leaders from tables of contents
    return " ".join(text.split())


def chunk_text(text: str, size: int = 800, overlap: int = 150) -> list[str]:
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


def ingest(path: str, skip_pages: int = 0) -> None:
    doc = fitz.open(path)
    rows = []  # (page number, chunk text)
    for page_no in range(skip_pages + 1, len(doc) + 1):
        text = clean(doc[page_no - 1].get_text())
        for chunk in chunk_text(text):
            if len(chunk) >= MIN_CHUNK:
                rows.append((page_no, chunk))

    if not rows:
        print("No text found. Is this a scanned PDF?")
        return

    embeddings = model.encode(
        [c for _, c in rows], batch_size=32,
        normalize_embeddings=True, show_progress_bar=True,
    )

    with psycopg.connect(DB_URL) as conn:
        register_vector(conn)
        doc_id = conn.execute(
            "INSERT INTO documents (name) VALUES (%s) RETURNING id",
            (pathlib.Path(path).name,),
        ).fetchone()[0]
        with conn.cursor() as cur:
            cur.executemany(
                "INSERT INTO chunks (document_id, page, content, embedding) "
                "VALUES (%s, %s, %s, %s)",
                [(doc_id, p, c, e) for (p, c), e in zip(rows, embeddings)],
            )
        conn.commit()
    print(f"Ingested {len(rows)} chunks from {path} (skipped first {skip_pages} pages)")


if __name__ == "__main__":
    skip = int(sys.argv[2]) if len(sys.argv) > 2 else 0
    ingest(sys.argv[1], skip)