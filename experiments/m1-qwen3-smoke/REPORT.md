# Local reproduction report

Local public-data reproduction; local judge is not calibrated against human experts

## Coverage

Selected: 4; generated: 4; valid grades: 4; failed grades: 0; truncated generations: 0.

**Overall (2:5:3): 82.33%**. This is a local-judge result, not a paper leaderboard replication.

## Task scores

| Task | Valid n | Earned / Maximum | Score % | Bootstrap 95% CI |
|---|---:|---:|---:|---|
| case_analysis | 1 | 45 / 60 | 75.00 | n < 2 |
| consultation | 1 | 16 / 16 | 100.00 | n < 2 |
| plaintiff | 1 | 78 / 100 | 78.00 | n < 2 |
| defendant | 1 | 70 / 80 | 87.50 | n < 2 |

Drafting average (equal plaintiff/defendant mean): 82.75%. Pooled drafting point rate, diagnostic only: 82.22%.

## Case dimensions

| Group | n | Score % |
|---|---:|---:|
| conclusion | 1 | 0.00 |
| facts | 1 | 100.00 |
| reasoning | 1 | 50.00 |
| statutes | 1 | 100.00 |

## Legal domains

| Group | n | Score % |
|---|---:|---:|
| 个人生活 | 1 | 75.00 |

## Reasoning and sequence

| Group | n | Score % |
|---|---:|---:|
| unspecified | 1 | 50.00 |

Explicit rubric constraints only; unspecified rows excluded from comparison. Groups differ in cases; this is not a causal ablation.

## Runtime and interpretation

Generation: 3.05 min; judging: 2.37 min. Generated tokens: 7,534; peak MLX allocator memory: 3.89 GB.

Seed-42 percentile bootstrap over questions, 1000 replicates, conditional on the local judge; does not measure judge correctness.

The local quantized candidate and local judge differ from the paper's full model/evaluator setup. Scores measure rubric agreement and may reward errors in the source rubrics. They are not a measure of current legal correctness.

Structural format failures: 3; judge retries: 0. See `error_analysis.json` for affected IDs and five lowest-scoring examples per task.

Inspect `predictions/`, `grades/`, `scores.csv`, both stage manifests and `dataset_manifest.json` for raw evidence.
