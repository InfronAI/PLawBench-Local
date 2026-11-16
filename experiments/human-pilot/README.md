# Human calibration materials

`annotation_materials.json` is exported from actual answers in `m1-public`.
It includes the original instructions, questions, responses and source rubrics.
`pilot_manifest.json` records the deterministic stratified sample selection.

The three expert columns in `ratings.csv` are intentionally **blank**. No expert
ratings or human correlation results are claimed. Reviewers should independently
score the supplied responses against the supplied instructions and rubric, using
percentage values from 0 to 100. Keep each sample ID and task unchanged.

Once all three real expert ratings are available, run from the project root:

```bash
plawbench calibrate --human experiments/human-pilot/ratings.csv \
  --judge experiments/m1-public/grades.jsonl \
  --output experiments/human-pilot/calibration.json
```

The command rejects blank ratings. The released consultation and drafting sets
are smaller than the paper's pilot targets; this is a public-data adaptation,
not a claim that the original three-expert study has been performed.
