# Findings from the complete public-data local run

**These are uncalibrated local-judge diagnostics. They are not validated legal capability measurements or a replication of the paper leaderboard.**

## Verified execution

All 280 public questions have actual saved model responses and valid rubric score records. Unresolved judge failures: 0; candidate responses stopped by the token budget: 1.

Candidate: `mlx-community/Qwen3-4B-Instruct-2507-4bit` at `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`. Judge: `mlx-community/Qwen3-4B-Instruct-2507-4bit` at `50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b`. The judge context includes the original generation instructions and source rubric. Both run locally through MLX on Apple M1 Pro / 16 GB; no inference API was used.

Candidate decoding/prefill accounted for 185.98 minutes; all judge attempts accounted for 357.05 minutes. The candidate produced 394,278 tokens. Maximum reported MLX allocator memory was 8.88 GB. These stage times exclude downloads, model loading and uncommitted interrupted batches. They are not a controlled performance comparison.

The main run includes a documented normalization correction: consultation-12 contains three original entries numbered 10. Unique positional IDs preserve all 12 criteria and all 33 points. The archived run supplied 280 unchanged candidate responses and 279 judgments with identical inputs; only the affected judgment was recomputed. The migration receipt and record hashes retain this provenance, including the three earlier failed attempts.

## Observed scoring pattern

The local weighted overall score is 79.99%. Each subset uses total earned points divided by total source maximum points. Drafting averages the two subtype rates equally; Overall weights consultation/cases/drafting at 2:5:3.

Among case dimensions, the largest local scoring rate is **facts (95.32%)** and the smallest is **conclusion (68.09%)**. This describes the selected judge's allocations, not independent legal correctness.

Across released case domains, `公司治理` has the highest observed rate (94.49%, n=25); `婚姻家事` the lowest (72.93%, n=22). Domain size and case composition differ. No causal domain-difficulty conclusion is warranted.

## Reasoning sequence groups

- unspecified: n=154, reasoning rate 79.25%.
- sequential: n=80, reasoning rate 73.65%.
- nonsequential: n=16, reasoning rate 69.61%.

Nonsequential minus sequential is -4.04 percentage points. These are different questions, with labels inferred only from explicit rubric wording. The comparison does not recreate an intervention on the same questions, nor the unavailable original group labels.

## Output requirements and judge reliability

Exact-title/order, consultation-number and drafting-length diagnostics flagged 230 answers: case_analysis=203, consultation=18, defendant=6, plaintiff=3. These checks do not override rubric scores.

18/18 consultation answers exceed the requested numbered-question limit. The largest count is 379 in `consultation-013`. Counts include repeated or restarted numbered lists, not just distinct questions. Raw responses remain intact; only the permitted leading questions are supplied to the judge.

Drafting outputs contain 2,381–4,620 non-whitespace characters. 3/12 meet the requested 2,500–3,000 range. This mechanical length check does not assess legal content.

The grader required 59 additional attempts to obtain valid score records. Valid JSON and in-range points establish structural validity, not evidence accuracy.

The conservative affirmative-citation screen flagged 37 claims in 21 answers out of 280 valid graded answers. See `judge_evidence_audit.json` for exact statements and IDs. Each flag requires manual review; alternative citation notation and complex statements may cause false positives. The scan neither checks current law nor proves unflagged judgments correct.

A saved textual review of 2 answers confirmed 3 unsupported citation attributions. See `judge_manual_audit.json` for the review scope, exact claims, candidate citation sections and file hashes. This checks attribution, not legal correctness or the appropriate score; the saved scores remain unchanged. Expanded instruction context therefore does not eliminate judge evidence errors.

## Limits and next reproducible step

Only 280 of the paper's 850 questions are public here. The original Gemini evaluator, 27-model comparison and real three-expert pilot were not reproduced. The CLI implements the reusable task, scoring, calibration and analysis workflows, but cannot supply missing private data or human judgments.

The prepared human pilot contains stratified actual model answers and blank expert rating fields. After real ratings are supplied, `plawbench calibrate` can compute per-task Pearson, tie-aware Spearman and MAE. Bootstrap intervals in the current report are conditional on the local judge and do not account for its bias.

See [the complete tables](../experiments/m1-public/REPORT.md), [protocol](REPRODUCTION.md), [data audit](DATA_QUALITY.md) and [M1 measurement notes](M1_NOTES.md).
