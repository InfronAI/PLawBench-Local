"""Point-weighted paper metrics, uncertainty, coverage and human-judge alignment."""
from collections import defaultdict, Counter
from pathlib import Path
import csv
import html
import json
import math
import random
import statistics

from .io import write_json, read_jsonl, digest
from .scoring import parse_scores
from .pipeline import export_records


def ratio(rows):
    denominator = sum(r["max_points"] for r in rows)
    return 100 * sum(r["points"] for r in rows) / denominator if denominator else None


def aggregate(rows):
    return {"n": len(rows), "points": sum(r["points"] for r in rows),
            "max_points": sum(r["max_points"] for r in rows), "score_percent": ratio(rows)}


def interval(rows, repetitions=1000):
    if len(rows) < 2:
        return None
    rng = random.Random(42)
    estimates = sorted(ratio(rng.choices(rows, k=len(rows))) for _ in range(repetitions))
    return [estimates[int(repetitions * .025)], estimates[int(repetitions * .975)]]


def summarize(samples, predictions, grades):
    by_id = {s["id"]: s for s in samples}
    valid = [g for g in grades if g["status"] == "ok"]
    tasks, dimensions, domains, sequence = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)
    for g in valid:
        s = by_id[g["id"]]
        tasks[s["task"]].append(g)
        if s["task"] == "case_analysis":
            domains[s["domain"]].append(g)
            for score in g["scores"]:
                dimensions[score["id"]].append(score)
                if score["id"] == "reasoning":
                    sequence[s["sequence"]].append(score)
    task_stats = {t: {**aggregate(rows), "bootstrap_95ci": interval(rows)} for t, rows in tasks.items()}
    drafting = aggregate(tasks["plaintiff"] + tasks["defendant"])
    drafting['pooled_score_percent'] = drafting['score_percent']
    # Table 3's Task3-Avg is the equal mean of the two drafting subset rates.
    drafting['score_percent'] = ((ratio(tasks['plaintiff']) + ratio(tasks['defendant'])) / 2
                                  if tasks['plaintiff'] and tasks['defendant'] else None)
    drafting['aggregation'] = 'equal mean of plaintiff and defendant point-weighted rates (Table 3)'
    complete = len(valid) == len(samples) and len(predictions) == len(samples)
    all_tasks = all(tasks.get(t) for t in ("consultation", "case_analysis", "plaintiff", "defendant"))
    overall = (.2 * ratio(tasks["consultation"]) + .5 * ratio(tasks["case_analysis"]) + .3 * drafting["score_percent"]
               if all_tasks and complete else None)
    gen_seconds = sum(p.get("elapsed_seconds", 0) for p in predictions)
    gen_tokens = sum(p.get("generation_tokens", 0) for p in predictions)
    judge_seconds = sum(a.get("elapsed_seconds", 0) for g in grades for a in g.get("attempts", []))
    generation_peak = max((p.get('peak_memory_gb',0) for p in predictions),default=0)
    judge_peak = max((a.get('peak_memory_gb',0) for g in grades for a in g.get('attempts',[])),default=0)
    question_counts = {p["id"]: p["format_check"] for p in predictions if "format_check" in p}
    for prediction in predictions:
        if by_id[prediction['id']]['task'] == 'case_analysis':
            headings = ['【结论】','【案件事实】','【推理过程】','【法条依据】']
            positions = [prediction['text'].find(h) for h in headings]
            question_counts[prediction['id']] = {
                'missing_headings':[h for h,i in zip(headings,positions) if i < 0],
                'within_requested_range':all(i >= 0 for i in positions) and positions == sorted(positions),
                'check':'Exact requested section titles and order; diagnostic only'}
    return {
        "scope": "Local public-data reproduction; local judge is not calibrated against human experts",
        "coverage": {"selected": len(samples), "generated": len(predictions), "graded": len(valid),
                     "judge_failed": sum(g["status"] != "ok" for g in grades),
                     "generation_truncated": sum(p.get("finish_reason") == "length" for p in predictions),
                     "grading_complete": complete, "full_public_dataset": len(samples) == 280},
        "overall_2_5_3_percent": overall, "tasks": task_stats, "drafting": drafting,
        "case_dimensions": {k: aggregate(v) for k, v in dimensions.items()},
        "domains": {k: aggregate(v) for k, v in domains.items()},
        "reasoning_by_sequence": {k: aggregate(v) for k, v in sequence.items()},
        "sequence_caveat": "Explicit rubric constraints only; unspecified rows excluded from comparison. Groups differ in cases; this is not a causal ablation.",
        "format_checks": question_counts,
        "runtime": {"generation_seconds": gen_seconds, "judge_seconds": judge_seconds,
                    "generation_tokens": gen_tokens, "end_to_end_tokens_per_second": gen_tokens / gen_seconds if gen_seconds else None,
                    "peak_memory_gb": max(generation_peak,judge_peak),
                    "generation_peak_memory_gb": generation_peak,
                    "judge_process_peak_memory_gb": judge_peak},
        "aggregation": "Subset rates = 100 * sum(earned points) / sum(dataset maxima); drafting = mean(plaintiff, defendant); Overall = .2 consultation + .5 case + .3 drafting",
        "uncertainty": "Seed-42 percentile bootstrap over questions, 1000 replicates, conditional on the local judge; does not measure judge correctness.",
    }


def report(samples, root):
    root = Path(root)
    predictions = export_records(root, "predictions", samples)
    grades = export_records(root, "grades", samples)
    smap = {s['id']:s for s in samples}
    pmap = {p['id']:p for p in predictions}
    for p in predictions:
        if p['response_sha256'] != digest(p['text']) or p['input_sha256'] != digest(smap[p['id']]['messages']):
            raise ValueError(f"Prediction integrity mismatch: {p['id']}")
    for g in grades:
        if g['id'] not in pmap or g['response_sha256'] != pmap[g['id']]['response_sha256']:
            raise ValueError(f"Grade belongs to a different prediction: {g['id']}")
        if g['status'] == 'ok':
            validated = parse_scores(g['attempts'][-1]['text'], smap[g['id']]['rubrics'])
            if validated != g['scores'] or g['points'] != sum(r['points'] for r in validated) or g['max_points'] != smap[g['id']]['max_points']:
                raise ValueError(f"Grade integrity mismatch: {g['id']}")
    summary = summarize(samples, predictions, grades)
    write_json(root / "summary.json", summary)
    valid = [g for g in grades if g['status'] == 'ok']
    errors = {
        'scope': 'Structural diagnostics and low-scoring examples; not an expert legal correctness review',
        'truncated_predictions': [p['id'] for p in predictions if p.get('finish_reason') == 'length'],
        'format_noncompliance': [{"id": sid, **check} for sid,check in summary['format_checks'].items()
                                if check.get('within_requested_range') is False],
        'judge_failures': [g['id'] for g in grades if g['status'] != 'ok'],
        'judge_retry_count': sum(max(0,len(g.get('attempts',[]))-1) for g in grades),
        'lowest_scoring_by_task': {task: [{"id":g['id'], "score_percent":100*g['points']/g['max_points'],
                                         "scores":g['scores']} for g in sorted(
            [x for x in valid if x['task']==task],key=lambda x:x['points']/x['max_points'])[:5]]
            for task in ['consultation','case_analysis','plaintiff','defendant']}}
    write_json(root / 'error_analysis.json', errors)
    with (root / "scores.csv").open("w", newline="") as f:
        out = csv.writer(f)
        out.writerow(["id", "task", "status", "points", "max_points", "score_percent"])
        for g in grades:
            out.writerow([g["id"], g["task"], g["status"], g.get("points"), g.get("max_points"),
                          100*g["points"]/g["max_points"] if g["status"] == "ok" else None])
    def fmt(value):
        return f"{value:.2f}" if value is not None else "unavailable"
    lines = ["# Local reproduction report", "", summary["scope"], "", "## Coverage", "",
             f"Selected: {len(samples)}; generated: {len(predictions)}; valid grades: {summary['coverage']['graded']}; "
             f"failed grades: {summary['coverage']['judge_failed']}; truncated generations: {summary['coverage']['generation_truncated']}.", "",
             f"**Overall (2:5:3): {fmt(summary['overall_2_5_3_percent'])}%**. This is a local-judge result, not a paper leaderboard replication.", "",
             "## Task scores", "", "| Task | Valid n | Earned / Maximum | Score % | Bootstrap 95% CI |",
             "|---|---:|---:|---:|---|" ]
    for task, row in summary["tasks"].items():
        ci = row["bootstrap_95ci"]
        lines.append(f"| {task} | {row['n']} | {row['points']:g} / {row['max_points']:g} | {fmt(row['score_percent'])} | "
                     + (f"{ci[0]:.2f}–{ci[1]:.2f}" if ci else "n < 2") + " |")
    lines += ['', f"Drafting average (equal plaintiff/defendant mean): {fmt(summary['drafting']['score_percent'])}%. "
              f"Pooled drafting point rate, diagnostic only: {fmt(summary['drafting']['pooled_score_percent'])}%."]
    for label, key in (("Case dimensions", "case_dimensions"), ("Legal domains", "domains"), ("Reasoning and sequence", "reasoning_by_sequence")):
        lines += ["", f"## {label}", "", "| Group | n | Score % |", "|---|---:|---:|"]
        lines += [f"| {k} | {v['n']} | {fmt(v['score_percent'])} |" for k,v in summary[key].items()]
    lines += ["", summary["sequence_caveat"], "", "## Runtime and interpretation", "",
              f"Generation: {summary['runtime']['generation_seconds']/60:.2f} min; judging: {summary['runtime']['judge_seconds']/60:.2f} min. "
              f"Generated tokens: {summary['runtime']['generation_tokens']:,}; peak MLX allocator memory: {summary['runtime']['peak_memory_gb']:.2f} GB.", "",
              summary["uncertainty"], "", "The local quantized candidate and local judge differ from the paper's full model/evaluator setup. "
              "Scores measure rubric agreement and may reward errors in the source rubrics. They are not a measure of current legal correctness.", "",
              f"Structural format failures: {len(errors['format_noncompliance'])}; judge retries: {errors['judge_retry_count']}. "
              "See `error_analysis.json` for affected IDs and five lowest-scoring examples per task.", "",
              "Inspect `predictions/`, `grades/`, `scores.csv`, both stage manifests and `dataset_manifest.json` for raw evidence.", ""]
    (root / "REPORT.md").write_text("\n".join(lines))
    pmap, gmap = {p["id"]: p for p in predictions}, {g["id"]: g for g in grades}
    data = {"summary": summary, "samples": [{**s, "prediction": pmap.get(s["id"]), "grade": gmap.get(s["id"])} for s in samples]}
    template = (Path(__file__).parent / "report.html").read_text()
    (root / "report.html").write_text(template.replace("__REPORT_DATA__", json.dumps(data, ensure_ascii=False).replace("<", "\\u003c")))
    return summary


def pearson(x, y):
    if len(x) < 2:
        return None
    ax, ay = statistics.mean(x), statistics.mean(y)
    xx, yy = sum((v-ax)**2 for v in x), sum((v-ay)**2 for v in y)
    return sum((a-ax)*(b-ay) for a,b in zip(x,y)) / math.sqrt(xx*yy) if xx and yy else None


def ranks(values):
    order = sorted(range(len(values)), key=values.__getitem__)
    result = [0.] * len(values)
    i = 0
    while i < len(values):
        j = i + 1
        while j < len(values) and values[order[j]] == values[order[i]]:
            j += 1
        for index in order[i:j]:
            result[index] = (i + 1 + j) / 2
        i = j
    return result


def calibrate(human_path, judge_path):
    # JSONL: {id, task, ratings:[0..100, ...]} and {id, task, score:0..100}.
    if Path(human_path).suffix.lower() == '.csv':
        with Path(human_path).open(encoding='utf-8-sig',newline='') as f:
            humans = list(csv.DictReader(f))
        for row in humans:
            try:
                row['ratings'] = [float(row[f'human_rating_{i}']) for i in range(1,4)]
            except (ValueError,KeyError) as exc:
                raise ValueError(f"Three actual expert ratings are required for {row.get('id')}; blank forms cannot be calibrated") from exc
    else:
        humans = read_jsonl(human_path)
    judges = read_jsonl(judge_path)
    for row in judges:
        if 'score' not in row:
            if row.get('status') != 'ok' or not isinstance(row.get('max_points'),(int,float)) or row['max_points'] <= 0:
                raise ValueError(f"Cannot calibrate failed/incomplete judge record: {row.get('id')}")
            row['score'] = 100 * row['points'] / row['max_points']
    if not humans or not judges:
        raise ValueError("Calibration requires real paired human and judge scores")
    for rows in (humans, judges):
        if len({r["id"] for r in rows}) != len(rows):
            raise ValueError("Duplicate calibration sample id")
    jmap = {r["id"]: r for r in judges}
    grouped = defaultdict(list)
    for h in humans:
        if h["id"] not in jmap:
            continue
        j = jmap[h["id"]]
        ratings = h["ratings"]
        if len(ratings) < 3:
            raise ValueError("Paper calibration requires at least three human ratings per answer")
        if h["task"] != j["task"]:
            raise ValueError("Calibration task mismatch")
        if not all(isinstance(v, (int,float)) and not isinstance(v,bool) and math.isfinite(v) and 0 <= v <= 100
                   for v in ratings + [j["score"]]):
            raise ValueError("Calibration scores must be finite numbers in [0, 100]")
        grouped[h["task"]].append((statistics.mean(ratings), j["score"]))
    if not grouped:
        raise ValueError("No matching calibration IDs")
    stats = {}
    for task, pairs in grouped.items():
        x, y = map(list, zip(*pairs))
        stats[task] = {"n": len(pairs), "pearson": pearson(x,y), "spearman": pearson(ranks(x),ranks(y)),
                       "mae": statistics.mean(abs(a-b) for a,b in pairs)}
    return {"tasks": stats, "unmatched_human_ids": sorted({h['id'] for h in humans}-set(jmap)),
            "unmatched_judge_ids": sorted(set(jmap)-{h['id'] for h in humans})}
