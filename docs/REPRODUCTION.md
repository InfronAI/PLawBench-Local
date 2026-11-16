# Reproduction scope and protocol

The reference is the [final ACL 2026 paper](https://aclanthology.org/2026.acl-long.458/), rather than a third-party adapter or an earlier abstract. The upstream repository baseline is `f6ee07b36c1f4c0bfc2af8ca27183d3dd3175c56`. Copies of the original executable scripts and README are in `docs/upstream/`; source datasets remain at their original paths.

## Coverage matrix

| Component | Implementation / evidence | Scope |
|---|---|---|
| Expert data collection and annotation | Preserve supplied scenarios and rubric text | 280 public items; private source material unavailable |
| Three legal tasks | Original Chinese generation prompts; four public subsets | Implemented |
| Local inference | MLX, native Metal, pinned 4-bit model, batch sizes 1–4 | Executed on M1 Pro / 16 GB |
| Rubric judging | All source criteria and penalties passed to judge; validated numeric allocations | Implemented with local Qwen3-4B |
| Four case dimensions | Conclusion, facts, reasoning, statutes | Implemented |
| Consultation question cutoff | Judge sees first 25 numbered questions by default; 50 for explicit hard mode | Implemented; no released difficulty labels |
| Overall metric | Point-weighted rates; task weights 2:5:3, final Table 3 | Implemented |
| Task/domain analysis | Per-task, dimension and released-domain summaries | Implemented |
| Sequence comparison | Explicit wording-derived groups, with unknowns retained | Partial: official per-question group labels unavailable |
| Human alignment | Pearson, tie-aware Spearman, MAE from at least three real expert ratings | Implemented, not executed without annotations |
| Published multi-model leaderboard | Original ranking preserved in upstream README | Not re-executed; original model access and full data absent |
| Original judge | Paper selects Gemini-3.0-Pro-Preview | Replaced with local self-judge; scores not directly comparable |
| Qualitative error analysis | Actual responses, grading rationales, format failures and low-scoring records | Local diagnostic evidence, not a new expert legal review |

The user's approved scope is completion of the public-data local reproduction. Unavailable data and expert annotations cannot be reconstructed faithfully by generating substitutes.

## Execution order

1. Inspect architecture and Metal availability with `plawbench doctor`.
2. Normalize all four original files; derive stable IDs and source SHA-256 hashes.
3. Preserve original generation prompts; provide no per-case rubric to the candidate.
4. Generate all selected answers, retaining token budgets, actual stop reasons, timing and model revision.
5. Pass each answer, the complete original generation instructions, the user scenario and its original rubric to the judge. Consultation responses are capped before grading.
6. Validate every expected rubric ID, numeric score, range and nonempty rationale. Retry malformed outputs within a fixed bound. Preserve all attempts.
7. Aggregate earned/max points in Python, not using the judge's arithmetic or denominator. Drafting takes the equal mean of the plaintiff and defendant rates: this is inferred from the Task3-Avg arithmetic in Table 3; a pooled-point alternative is retained for transparency.
8. Export tables and an interactive, self-contained report. Inspect incomplete coverage and output-length failures explicitly.

`configs/m1-public.json` documents the checked-in full run; `scripts/reproduce.sh` executes the same settings. Different models are loaded one at a time; an identical candidate/judge is reused. The allocator cache is capped at 128 MiB, with a 6 GiB allocation guideline and active-memory checks. Generation batches have at most four active completions; judging uses two sequences because its contexts include both instructions and rubrics. Both stages prefill one prompt at a time, in 512-token chunks. No prompt or KV history is deliberately truncated. In a batch, wall time is divided evenly between records for additive stage accounting; `completion_latency_seconds` and `batch_wall_seconds` retain the actual latency information.

The selected model is in the paper's evaluated family. Quantization, greedy sampling, local judging, public-only coverage, compact judge JSON and inferred sequence groups differ from the paper. A 16,384-token upper bound matches the lower generation budget stated in §4.1; a normal EOS ends generation earlier. Judge retries use temperature 0.2 after the first greedy attempt. GPU floating-point reductions and different batch membership can prevent bit-identical text across interrupted and fresh runs despite fixed seeds.

## Published-table arithmetic note

The drafting macro average is inferred from the plaintiff/defendant arithmetic in the table's usual rows; the final paper explicitly specifies only the Overall 2:5:3 weights in the table caption. One published row is internally inconsistent: GPT-5.2 lists Task3-Avg 68.58 with component values 58.25 and 63.42 (whose mean is 60.835). The original table is preserved, not silently corrected. Private raw scores are unavailable to resolve that discrepancy. This implementation states its drafting equal-mean policy explicitly and also exports the pooled-point alternative.

## Human-judge calibration

Create a deterministic stratified pilot and **blank** three-expert rating forms from actual predictions:

```bash
plawbench pilot --run experiments/m1-public --output experiments/human-pilot
```

This samples ceil(10%) from each released case domain, up to 20 consultations and up to 10 documents per subtype. The release has only 18/6/6 of the latter tasks, and only one local candidate is used; these limitations are recorded. `annotation_materials.json` contains the original generation instructions, questions, answers and rubrics; `ratings.csv` contains empty score fields. The command does not assign human scores.

After experts fill the CSV with percentage scores, the actual artifact formats connect directly:

```bash
plawbench calibrate --human experiments/human-pilot/ratings.csv --judge experiments/m1-public/grades.jsonl --output experiments/human-pilot/calibration.json
```

Blank ratings and failed judge records are rejected. Alternatively, provide the following JSONL schemas.

Human JSONL records:

```json
{"id":"case_analysis-001","task":"case_analysis","ratings":[61,63,62]}
```

Candidate-judge JSONL records:

```json
{"id":"case_analysis-001","task":"case_analysis","score":60}
```

These numbers illustrate the schema only; they are not experiment observations. Scores must be percentages in [0,100]. At least three ratings are required per answer. IDs must be unique and task labels must agree. Results are grouped by task; unmatched IDs are reported. Correlation is `null` for fewer than two paired answers or constant scores. To compare evaluator candidates, run `calibrate` once per candidate using the same human file. A full paper-style pilot also requires domain coverage and appropriate answer sampling; the command does not manufacture those conditions.

## Artifact interpretation

The `m1-smoke` directory records the smaller Qwen2.5-1.5B diagnostic candidate and demonstrates its generation failures. The `m1-qwen3-smoke` directory contains four completed preliminary Qwen3 candidate/judge examples under the initial compact judge context. The final full run additionally passes the original generation instructions to the judge, so the smoke scores should not be compared directly with full-run scores. The full experiment is `m1-public`. Smoke examples are the first row of each subset and are not representative random samples. Never combine their scores with the complete release or call fixture-based unit tests model experiments.

Raw model statements and rubric text can be legally incorrect, outdated or internally contradictory. The pipeline evaluates agreement with the release and preserves evidence for review; it does not correct or endorse legal claims. See [data quality notes](DATA_QUALITY.md).

## Observed judge reliability limitation

A direct text audit of preliminary smoke case `case_analysis-001` found that the local judge awarded the statutes dimension 15/15 while claiming that the answer cited articles 509, 996 and 1183. Those citations (checked in both Arabic and Chinese numeral forms) are absent from the candidate's answer. The exact rationale and checks are saved in `experiments/m1-qwen3-smoke/judge_audit.json`. This establishes an evidence-grounding failure without requiring any claim about which law is legally correct.

Therefore local scores are **uncalibrated diagnostics**, not validated estimates of legal competence or evidence of outperforming the paper's models. The full run uses the expanded original instruction context, but this does not establish judge reliability. Real expert review and candidate-judge alignment remain necessary. No score is silently corrected or replaced by a fabricated expert label.
