# Experiment evidence

The canonical public-data reproduction is [`m1-public/`](m1-public/REPORT.md).
Read its coverage counts and [`verification.json`](m1-public/verification.json)
before interpreting scores. All model statements and judge rationales are raw
evidence; the local self-judge is not calibrated against legal experts.

| Directory | Purpose | Interpretation |
|---|---|---|
| `m1-public` | All 280 released questions, pinned Qwen3-4B candidate and local judge | Main reproduction; original instructions included in judge context |
| `m1-public-before-rubric-id-fix` | Preserved run before correcting consultation-12 duplicate IDs | Provenance for reused inputs/outputs and the original failed attempts |
| `public-audit` | Normalized public data, source hashes and schema issues | Data audit; no model score |
| `m1-qwen3-smoke` | Four Qwen3 task examples with preliminary judge context | Pipeline check; not comparable to the final run's scores |
| `m1-smoke` | Four Qwen2.5-1.5B generations | Records repetition and truncation; not a complete scoring experiment |
| `m1-batch4-aborted` | Interrupted initial memory investigation | No completed predictions; not a benchmark result |
| `m1-batch2-check` | Two generations after allocator controls | Memory feasibility check, not a controlled speed comparison |
| `human-pilot` | Stratified real answers and blank three-expert forms | No fabricated expert ratings or correlation results |
| `validation` | Unit tests, environment and installation checks | Software verification, not model performance |

The main run saves each response and every grading attempt separately. JSONL
exports provide a convenient combined copy; the report is a standalone HTML
file. `artifact_checksums.json` binds the final analysis files to their exact
contents. The source datasets and pretrained weights are not copied into each
experiment; source hashes and pinned model file hashes identify them instead.
