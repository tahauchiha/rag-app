import sys
import ollama
from retrieval import rerank_search

MODEL = "llama3.2:3b"
TOP_K = 5

SYSTEM = (
    "You answer questions using ONLY the numbered context passages provided. "
    "Every answer MUST end with a source line in exactly this form: "
    "'Source: p. N' where N is the page of the passage you used. "
    "If the context does not contain the answer, reply exactly: "
    "'I could not find this in the document.' Do not use outside knowledge."
)


def answer(question: str, add_sources: bool = False) -> str:
    chunks = rerank_search(question, k=TOP_K)
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
    text = resp["message"]["content"]

    if add_sources and "could not find this" not in text.lower():
        pages = list(dict.fromkeys(p for p, _ in chunks[:3]))  # top 3 pages, rank order
        text += "\n\nRetrieved from: " + ", ".join(f"p. {p}" for p in pages)
    return text


if __name__ == "__main__":
    print(answer(sys.argv[1], add_sources=True))