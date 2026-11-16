# Public release audit and compatibility changes

No original JSON/JSONL dataset has been rewritten. Exact source hashes are recorded in every dataset manifest. Normalization and exceptions are visible in code and artifacts.

| Observation | Original behavior / risk | Resolution |
|---|---|---|
| Consultation uses `conversation` | Generator accesses nonexistent `system.question` | Use actual released field |
| All consultation `score` fields are empty | Evaluator expects numeric total | Derive total from explicit (+N分) allocations |
| Consultation 12 has three distinct entries numbered 10 | Source-number IDs collide and prevent complete grading | Assign positional IDs q1–q12; preserve all original text and the full 33-point denominator |
| Consultation 17 header says 12, items sum to 13 | Conflicting denominator | Use sum 13; emit manifest issue |
| Case 1 statutes allocation is 15 but positive text lists four 5-point clauses | Internal rubric discrepancy | Preserve text and structured maximum 15; judge cannot change denominator |
| Plaintiff 5 category headers sum to 95 but `score` says 100 | Drafting maximum discrepancy | Preserve structured `score` 100 and raw rubric; flag for expert review |
| No released consultation difficulty labels | Original code switches to hard at index 50, never reached in 18 rows | Default all to mid; explicit `--consultation-level hard` changes protocol |
| Worked case example overlaps case 20 (L某/R某 property dispute) | Candidate prompt contains related reference reasoning | Preserve original prompt for comparability; disclose contamination |
| No official sequence label field | Guessing all unmarked rows as nonsequential biases analysis | Explicit-constraint groups plus `unspecified`; local partial swaps are not global labels |
| Original scripts execute on import / use `your_path` | Cannot import or run on a clean checkout | Import-safe CLI; paths resolved from checkout or explicit argument |
| Judge API function is empty | No actual scoring | Native local model backend |
| Original case-judge JSON misses a comma and hard-codes conclusion 0/0 | Parsing errors / lost conclusion score | Explicit rubric IDs, fixed source maxima and strict validation |
| JSON repair accepts incomplete data | Missing fields may appear as valid zero scores | Only wrappers/trailing commas recovered; missing or nonfinite scores fail |
| Model returns wrong totals | Inflated or distorted metrics | Python computes all totals from validated points and source denominators |

The report also flags candidate truncation, question counts and drafting character counts. Question counting recognizes numbered lines, including common Markdown bold prefixes. Unnumbered output is reported as noncompliant rather than assigned an invented item count. Counting is a structural diagnostic; the expert rubric remains the scoring authority.

Some original defense rubrics conflict with facts stated in the scenario or reward contested legal/ethical positions. This implementation deliberately preserves the benchmark for reproducibility. Neither the source rubrics nor generated answers should be treated as verified legal advice.

The consultation-12 collision was discovered during the full local experiment. The first normalization version is preserved in `experiments/m1-public-before-rubric-id-fix/`. The corrected main run reuses only verified identical inputs: all 280 candidate responses and 279 valid judgments. Consultation-12 is judged again with unique IDs; its three earlier failed attempts remain labeled in the new record for provenance and runtime accounting. `normalization_migration.json` identifies every source record, and `scripts/check_artifacts.py` verifies the preserved payloads and hashes. No source dataset or awarded score is manually rewritten.
