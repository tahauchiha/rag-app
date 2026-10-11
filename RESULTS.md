# Evaluation results

Document: a civil engineering thesis (102 pages) on the durability of foam concrete containing ceramic tile waste powder (CTWP) and construction and demolition recycled fine aggregate (CD-RFA).

Pipeline: PyMuPDF text extraction (dot leaders removed, first 15 pages skipped, chunks under 150 characters dropped), 800-character chunks with 150 overlap, `all-MiniLM-L6-v2` embeddings (384-dim) in pgvector, Postgres full-text search, reciprocal rank fusion (RRF), `cross-encoder/ms-marco-MiniLM-L-6-v2` reranking of the top 20, and `llama3.2:3b` through Ollama for answers (temperature 0).

## Method

- **Development set:** `eval.json`, 27 questions. 23 are answerable and are labelled with the PDF page(s) that contain the answer plus short `must_contain` strings. 4 are unanswerable. In this thesis the PDF page number equals the printed page number.
- **Question mix:** exact-detail questions (test parameters, standards, table values) and conceptual questions (mechanisms, conclusions).
- **Page hit@k:** a labelled page appears in the top k results.
- **Answer hit@k (headline metric):** a top-k chunk contains one of the question's `must_contain` strings, compared case-insensitively with whitespace removed. This measures whether the answer text reached the model, which matters more than which page it came from.
- **Held-out set:** `eval_holdout.json`, 8 answerable and 2 unanswerable questions written after the pipeline was built. Not run yet (see below).

## Retrieval results (23 answerable questions)

Answer hit@k:

| Method | @1 | @3 | @5 | @20 |
|---|---|---|---|---|
| Vector only | 10/23 (43%) | 11/23 (48%) | 12/23 (52%) | 20/23 (87%) |
| Full-text only | 14/23 (61%) | 15/23 (65%) | 16/23 (70%) | 21/23 (91%) |
| Hybrid (RRF) | 11/23 (48%) | 15/23 (65%) | 17/23 (74%) | 22/23 (96%) |
| Hybrid + cross-encoder rerank | 17/23 (74%) | 21/23 (91%) | 21/23 (91%) | 22/23 (96%) |

Page hit@k:

| Method | @1 | @3 | @5 | @20 |
|---|---|---|---|---|
| Vector only | 10/23 (43%) | 12/23 (52%) | 15/23 (65%) | 22/23 (96%) |
| Full-text only | 14/23 (61%) | 15/23 (65%) | 15/23 (65%) | 21/23 (91%) |
| Hybrid (RRF) | 9/23 (39%) | 15/23 (65%) | 17/23 (74%) | 22/23 (96%) |
| Hybrid + cross-encoder rerank | 15/23 (65%) | 20/23 (87%) | 21/23 (91%) | 22/23 (96%) |

Findings:

- Embedding-only search was the weakest on this document, which is full of exact terms (voltages, standard codes, numeric results).
- Hybrid search raised recall at @5 and @20 but had worse @1 than full-text alone: equal-weight fusion let the weaker vector ranking pull down good keyword hits.
- The answer was inside the hybrid top 20 for 22 of 23 questions but inside the top 5 for only 17, so the main problem was ranking, not recall. That motivated the reranker, which raised answer hit@5 from 17 to 21 of 23. It cannot add candidates, which is why @20 is unchanged.
- The one remaining answer-metric miss (which factor governed chloride resistance) is probably a metric artifact: the model answered it correctly from retrieved text, but the finding is phrased differently across pages from my `must_contain` string.

Original strict-label baseline for vector search (before label corrections), page hit: @1 9/23, @3 11/23, @5 13/23.

## End-to-end results (reranked top 5, `llama3.2:3b`, CPU)

| Prompt | Unanswerable refused | Answerable but refused | Answerable with page cited by model | Answered, no citation | Avg time per answer |
|---|---|---|---|---|---|
| Original ("cite the page for every claim") | 4/4 | 1/23 | 17/23 | 5/23 | 15.5 s and 16.9 s (two runs) |
| Mandatory "Source: p. N" line | 4/4 | 0/23 | 18/23 | 5/23 | 21.3 s |

- Citation formatting is unreliable for a 3B model: the stricter prompt changed which questions were uncited, not how many.
- The `add_sources` option in `answer.py` appends a "Retrieved from" line built from the retrieved chunks, so the interface always shows pages. These are the pages the answer was retrieved from, not proof that the model verified each claim.
- Time per answer includes retrieval, reranking and generation on a laptop CPU.

## Manual grading (all 23 answerable questions, stricter-prompt run)

Each answer was read against the thesis text. Details were checked, not just the headline fact. Per-question grades and notes are in `grades.json`; `python grade_summary.py` merges them with `answers.json` and prints the counts.

| Grade | Count |
|---|---|
| Correct | 20 |
| Partial | 2 |
| Wrong | 1 |

| Question | Grade | Why |
|---|---|---|
| Abrasion loss at 70% CTWP vs the ASTM C131 limit | partial | 58.9% and the 35% limit are right, but the answer says 58.9% is "more than three times the limit". The thesis says more than three times the *control*; 58.9% is about 1.7 times the limit. |
| Recommended CTWP and CD-RFA replacement levels | partial | Returns the abrasion-specific advice (p. 87) and misses the overall recommendation of 10 to 20% CTWP with 10 to 20% CD-RFA (p. 100). |
| RCPT charge for 20% CTWP + 30% CD-RFA | wrong | Expected 3490.7 C (Moderate, p. 65). The model gave 4058.8 and 4696.6, which belong to other rows, and cited p. 66. |

Citation check on the 18 answers where the model cited a page: 16 cite a page that supports the stated content; 2 do not. The future-extension answer is correct but cites p. 101 (the reference list) instead of p. 99, and the table answer cites p. 66 for values that are on p. 65.

Caveats:
- The same AI assistant that helped write the questions also graded the answers, against a text extraction of the PDF. A human spot-check is needed, especially of the two partial grades and the five answers that cite no page.
- The three problems are all detail errors in otherwise fluent answers: a wrong comparison, a missed overall conclusion, and a misread table. A fluent, confident, cited answer can still be wrong, so answers need verification against the source.

## Failure analysis

| Problem | Cause |
|---|---|
| Table lookups are unreliable | PDF tables are extracted as a flat string of cells with no row structure. Retrieval found the right chunk, but the model matched values to the wrong rows. Possible fix: extract tables with PyMuPDF `find_tables()` and index each row as a sentence. Not tried yet. |
| Answer split across a page boundary | Chunks never cross pages, so facts near a boundary can fall into a neighbouring chunk. |
| Vocabulary mismatch ("voltage and duration" vs "60 V DC potential for 6 hours") | Neither embeddings nor keywords match well. Improved by reranking. |
| Same fact on several pages | Page-based labels are too narrow; the answer-string metric was added for this reason. |
| Uncited answers | A 3B model skips citation formatting on short lookup questions. |

Earlier ingestion problem: the first version indexed the table of contents (dot leaders), declaration pages and short figure captions, and these ranked highly for real questions. Cleaning, skipping front matter, dropping short chunks and switching from pypdf to PyMuPDF removed them. This was not measured with hit@k.

## Change log (everything changed after seeing results)

1. Switched PDF extraction from pypdf to PyMuPDF, removed dot leaders, skipped the first 15 pages, dropped chunks under 150 characters (after inspecting retrieval output).
2. Corrected three page labels because the answer genuinely appears on several pages (verified by searching the thesis text): water absorption standard (58, 67, 70, 71, 101), which acid caused greater mass loss (91, 93, 96, 99), recommended replacement levels (99, 100).
3. Added page 62 to the "by how much did the RCPT charge fall" question after finding "6537.9" and "53%" there.
4. Added the `must_contain` answer-string metric because page labels were too strict.
5. Added hybrid search, then a cross-encoder reranker, after seeing recall@20 results.
6. Changed the answer prompt to require a "Source: p. N" line after seeing uncited answers.
7. Added an optional "Retrieved from" line built from retrieval results.

Because these changes were made while looking at the same 23 questions, the development numbers are optimistic. The held-out set exists to correct that.

## Held-out set (not run yet)

`eval_holdout.json` has 8 answerable and 2 unanswerable questions about materials, mix design, results and future work. Run once, after the pipeline is final:

```
python -c "from retrieval import *; evaluate(rerank_search, 'rerank', path='eval_holdout.json')"
```

| Method | Answer hit@1 | Answer hit@3 | Answer hit@5 |
|---|---|---|---|
| Hybrid + rerank, held-out | TODO | TODO | TODO |

Note: the holdout string "ACI 523R" also matches the reference list on page 101, which would count as a hit even though a reference entry is not an answer.

## Limitations

- 23 development questions and 8 held-out questions, so one question moves a result by about 4 to 12 points.
- One document, one embedding model, one reranker, one 3B local LLM.
- Questions, labels and answer strings were written by the author with help from an AI assistant and checked against the PDF text.
- Chunks are scored by whether they contain a string, not by whether the model's final answer is correct.
- Answer grades come from a single grader (see the caveats above), on one run of one model.
- Latency was measured on a laptop CPU with other programs running.