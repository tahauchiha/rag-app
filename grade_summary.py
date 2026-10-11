import json
from collections import Counter

with open("answers.json", encoding="utf-8") as f:
    records = [r for r in json.load(f) if r["type"] == "answerable"]

try:
    with open("grades.json", encoding="utf-8") as f:
        manual = json.load(f)
except FileNotFoundError:
    manual = {}

for r in records:
    m = manual.get(r["q"], {})
    r["grade"] = r["grade"] or m.get("grade", "")
    r["notes"] = r["notes"] or m.get("notes", "")
    r["citation"] = m.get("citation", "")

grades = Counter(r["grade"] or "ungraded" for r in records)
print(f"Answerable questions: {len(records)}")
for g in ("correct", "partial", "wrong", "ungraded"):
    print(f"  {g:<9} {grades.get(g, 0)}")

cited = [r for r in records if r["cited"]]
bad = [r for r in cited if r["citation"] == "wrong"]
print(f"\nModel-cited answers: {len(cited)}; citation does not support the claim: {len(bad)}")

for r in records:
    if r["grade"] in ("partial", "wrong") or r["citation"] == "wrong":
        print(f"\n[{r['grade'].upper()}] {r['q']}\n  {r['notes']}")