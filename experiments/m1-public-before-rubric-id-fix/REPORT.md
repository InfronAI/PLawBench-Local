# Local reproduction report

Local public-data reproduction; local judge is not calibrated against human experts

## Coverage

Selected: 280; generated: 280; valid grades: 279; failed grades: 1; truncated generations: 1.

**Overall (2:5:3): unavailable%**. This is a local-judge result, not a paper leaderboard replication.

## Task scores

| Task | Valid n | Earned / Maximum | Score % | Bootstrap 95% CI |
|---|---:|---:|---:|---|
| case_analysis | 250 | 15285 / 18590 | 82.22 | 79.19–85.13 |
| consultation | 17 | 228 / 303 | 75.25 | 57.59–90.40 |
| plaintiff | 6 | 442 / 575 | 76.87 | 61.96–89.03 |
| defendant | 6 | 441 / 480 | 91.88 | 85.61–96.22 |

Drafting average (equal plaintiff/defendant mean): 84.37%. Pooled drafting point rate, diagnostic only: 83.70%.

## Case dimensions

| Group | n | Score % |
|---|---:|---:|
| conclusion | 250 | 68.09 |
| facts | 250 | 95.32 |
| reasoning | 250 | 76.78 |
| statutes | 250 | 83.82 |

## Legal domains

| Group | n | Score % |
|---|---:|---:|
| 个人生活 | 22 | 81.61 |
| 婚姻家事 | 22 | 72.93 |
| 诉讼仲裁 | 31 | 84.35 |
| 公司治理 | 25 | 94.49 |
| 劳动人事 | 22 | 85.95 |
| 刑事实务 | 25 | 75.19 |
| 知识产权 | 19 | 86.99 |
| 环保安全 | 14 | 83.35 |
| 法律科技 | 11 | 79.38 |
| 跨国事务 | 29 | 83.44 |
| 法律时效敏感度 | 15 | 86.09 |
| 法律理论应用 | 15 | 77.94 |

## Reasoning and sequence

| Group | n | Score % |
|---|---:|---:|
| unspecified | 154 | 79.25 |
| sequential | 80 | 73.65 |
| nonsequential | 16 | 69.61 |

Explicit rubric constraints only; unspecified rows excluded from comparison. Groups differ in cases; this is not a causal ablation.

## Runtime and interpretation

Generation: 185.98 min; judging: 356.55 min. Generated tokens: 394,278; peak MLX allocator memory: 8.88 GB.

Seed-42 percentile bootstrap over questions, 1000 replicates, conditional on the local judge; does not measure judge correctness.

The local quantized candidate and local judge differ from the paper's full model/evaluator setup. Scores measure rubric agreement and may reward errors in the source rubrics. They are not a measure of current legal correctness.

Structural format failures: 230; judge retries: 58. See `error_analysis.json` for affected IDs and five lowest-scoring examples per task.

Inspect `predictions/`, `grades/`, `scores.csv`, both stage manifests and `dataset_manifest.json` for raw evidence.
