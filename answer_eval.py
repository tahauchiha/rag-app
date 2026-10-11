import json
import re
import time
from answer import answer

REFUSAL = "could not find this in the document"
# matches "(p. 12)", "(p 12)", "(pages 12, 13)", "page 12", "p.12"
CITATION = re.compile(r"\b(?:pages?|pp?\.?)\s*\d+", re.IGNORECASE)

with open("eval.json", encoding="utf-8") as f:
    items = json.load(f)

unans = [x for x in items if not x["pages"]]
ans = [x for x in items if x["pages"]]
records = []

# --- unanswerable questions: the model should refuse -------------------------
correct_refusals = 0
for it in unans:
    out = answer(it["q"])
    refused = REFUSAL in out.lower()
    correct_refusals += refused
    records.append({"type": "unanswerable", "q": it["q"], "refused": refused, "answer": out})
    print(f"[{'OK ' if refused else 'BAD'}] refusal test: {it['q']}\n      {out[:150]}")

# --- answerable questions: should answer, with a page cited -----------------
false_refusals = []
uncited = []
cited = 0
times = []
for it in ans:
    t0 = time.time()
    out = answer(it["q"])
    times.append(time.time() - t0)

    refused = REFUSAL in out.lower()
    has_cite = bool(CITATION.search(out))
    if refused:
        false_refusals.append(it["q"])
    elif has_cite:
        cited += 1
    else:
        uncited.append(it["q"])

    records.append({
        "type": "answerable",
        "q": it["q"],
        "expected_pages": it["pages"],
        "must_contain": it.get("must_contain", []),
        "refused": refused,
        "cited": has_cite,
        "answer": out,
        # fill these in by hand after reading the answer against the thesis:
        "grade": "",   # correct / partial / wrong
        "notes": "",
    })
    status = "REFUSED" if refused else ("cited" if has_cite else "NO CITATION")
    print(f"[{status}] {it['q']}")

# --- save everything so it can be read and graded ---------------------------
with open("answers.json", "w", encoding="utf-8") as f:
    json.dump(records, f, indent=2, ensure_ascii=False)

print(f"\nUnanswerable correctly refused: {correct_refusals}/{len(unans)}")
print(f"Answerable but refused:         {len(false_refusals)}/{len(ans)}")
print(f"Answerable with a page cited:   {cited}/{len(ans)}")
print(f"Answerable, answered, no cite:  {len(uncited)}/{len(ans)}")
print(f"Avg time per answer:            {sum(times) / len(times):.1f}s")

if false_refusals:
    print("\nFalse refusals:")
    for q in false_refusals:
        print(f"  - {q}")
if uncited:
    print("\nAnswered without a page citation:")
    for q in uncited:
        print(f"  - {q}")

print("\nSaved all answers to answers.json. Open it and fill in 'grade' and 'notes'.")