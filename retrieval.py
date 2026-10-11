import json
import re
import psycopg
from pgvector.psycopg import register_vector
from sentence_transformers import SentenceTransformer, CrossEncoder

DB_URL = "postgresql://app:app@localhost:5433/rag"
embedder = SentenceTransformer("all-MiniLM-L6-v2")
reranker = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

def _vector(question: str, k: int):
    q_emb = embedder.encode(question, normalize_embeddings=True)
    with psycopg.connect(DB_URL) as conn:
        register_vector(conn)
        return conn.execute(
            "SELECT id, page, content FROM chunks ORDER BY embedding <=> %s LIMIT %s",
            (q_emb, k),
        ).fetchall()


def _fts(question: str, k: int):
    words = re.findall(r"[A-Za-z0-9]+", question)
    if not words:
        return []
    tsq = " | ".join(words)  # OR the words; stop words are dropped by Postgres
    with psycopg.connect(DB_URL) as conn:
        return conn.execute(
            "SELECT id, page, content FROM chunks "
            "WHERE tsv @@ to_tsquery('english', %s) "
            "ORDER BY ts_rank_cd(tsv, to_tsquery('english', %s)) DESC LIMIT %s",
            (tsq, tsq, k),
        ).fetchall()


def vector_search(question: str, k: int = 5):
    return [(p, c) for _, p, c in _vector(question, k)]


def fts_search(question: str, k: int = 5):
    return [(p, c) for _, p, c in _fts(question, k)]


def hybrid_search(question: str, k: int = 5, pool: int = 20, rrf_k: int = 60):
    """Reciprocal Rank Fusion: score = sum of 1 / (rrf_k + rank) over both lists."""
    scores, info = {}, {}
    for results in (_vector(question, pool), _fts(question, pool)):
        for rank, (cid, page, content) in enumerate(results, start=1):
            scores[cid] = scores.get(cid, 0) + 1 / (rrf_k + rank)
            info[cid] = (page, content)
    best = sorted(scores, key=scores.get, reverse=True)[:k]
    return [info[cid] for cid in best]

def rerank_search(question: str, k: int = 5, pool: int = 20):
    """Hybrid retrieval for candidates, then a cross-encoder rescoring pass."""
    candidates = hybrid_search(question, k=pool, pool=pool)
    scores = reranker.predict([(question, content) for _, content in candidates])
    ranked = sorted(zip(scores, candidates), key=lambda x: x[0], reverse=True)
    return [cand for _, cand in ranked[:k]]


def _norm(s: str) -> str:
    # lowercase and drop all whitespace, so extractor spacing differences don't matter
    return re.sub(r"\s+", "", s).lower()


def evaluate(search_fn, name, path="eval.json", ks=(1, 3, 5, 20), verbose=False):
    """Two metrics per method:
    page hit@k   - a labelled page appears in the top k results
    answer hit@k - a top-k chunk contains one of the question's must_contain strings
    """
    with open(path, encoding="utf-8") as f:
        items = [x for x in json.load(f) if x["pages"]]  # answerable only

    page_hits = {k: 0 for k in ks}
    ans_hits = {k: 0 for k in ks}
    ans_misses = []
    for it in items:
        results = search_fn(it["q"], max(ks))
        wanted = [_norm(s) for s in it.get("must_contain", [])]
        for k in ks:
            top = results[:k]
            if {p for p, _ in top} & set(it["pages"]):
                page_hits[k] += 1
            if any(w in _norm(c) for _, c in top for w in wanted):
                ans_hits[k] += 1
        if not any(w in _norm(c) for _, c in results for w in wanted):
            ans_misses.append((it["q"], [p for p, _ in results]))

    n = len(items)
    fmt = lambda h: "  ".join(f"@{k}: {h[k]}/{n} ({h[k] / n:.0%})" for k in ks)
    print(f"{name:<10} page   {fmt(page_hits)}")
    print(f"{'':<10} answer {fmt(ans_hits)}")
    if verbose:
        for q, got in ans_misses:
            print(f"   NO ANSWER IN TOP {max(ks)}: {q}\n     pages returned {got}")


if __name__ == "__main__":
    evaluate(vector_search, "vector")
    evaluate(fts_search, "full-text")
    evaluate(hybrid_search, "hybrid")
    evaluate(rerank_search, "rerank", verbose=True)