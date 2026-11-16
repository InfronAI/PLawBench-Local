"""Normalize the public release without changing original files or rubric text."""
from collections import Counter
from pathlib import Path
import json
import re

from .io import digest, file_hash
from .templates import prompt_template_dict, user_prompt_dict

FILES = {
    "case_analysis": "practical_case_analysis_250.jsonl",
    "consultation": "public_legal_consultation_18.json",
    "plaintiff": "Plantiffs_Statement.json",
    "defendant": "Defendants_Statement.json",
}
DIMENSIONS = {"结论得分": "conclusion", "案情简述得分": "facts",
              "分析过程得分": "reasoning", "法条依据得分": "statutes"}


def default_data_dir():
    import os
    if os.environ.get("PLAWBENCH_DATA"):
        return Path(os.environ["PLAWBENCH_DATA"])
    for p in (Path.cwd(), Path(__file__).resolve().parents[2]):
        if all((p / f).exists() for f in FILES.values()):
            return p
    raise ValueError("Data not found. Run from the repository or use --data-dir /path/to/PLawBench.")


def sequence_label(text):
    # Only explicit constraints; merely mentioning 'order' or using steps is not sufficient.
    head = text[:350]
    if re.search(r"(?:不|未)按.{0,20}顺序.{0,12}不得分|不得顺序调换|顺序.{0,8}(?:错误|不可).{0,8}|按.{0,6}步骤.{0,8}才能得分", head):
        return "sequential"
    if re.search(r"(?:按|依|必须|需要).{0,20}顺序.{0,15}(?:才可|否则|必须)|按以下步骤", head):
        return "sequential"
    # A local allowance for swapping only steps 2/3 says nothing about the whole chain.
    if re.search(r"第.{0,12}步.{0,8}顺序无要求", head[:100]):
        return "unspecified"
    if re.search(r"(?:无[需须]?|没有|不限|无需严格).{0,6}顺序|不按顺序.{0,6}(?:也可|可得)|不[分论]顺序", head):
        return "nonsequential"
    if re.search(r"(?:按|依|遵|遵循|必须|需要).{0,16}顺序|顺序.{0,18}(?:得分|推理)", head):
        return "sequential"
    return "unspecified"


def load_dataset(directory=None, consultation_level="mid"):
    root = Path(directory) if directory else default_data_dir()
    if consultation_level not in ("mid", "hard"):
        raise ValueError("consultation_level must be mid or hard")
    samples, issues = [], []
    for task, filename in FILES.items():
        path = root / filename
        rows = ([json.loads(line) for line in path.read_text().splitlines() if line.strip()]
                if path.suffix == ".jsonl" else json.loads(path.read_text()))
        for index, raw in enumerate(rows, 1):
            sid = f"{task}-{index:03}"
            if task == "case_analysis":
                system = prompt_template_dict[task]
                user = user_prompt_dict[task].format(**raw)
                rubrics = [{"id": DIMENSIONS[r["tags"]], "max_points": float(r["points"]),
                            "text": r["criterion"]} for r in raw["rubrics"]]
                group = raw["label"]
                sequence = sequence_label(next(r["text"] for r in rubrics if r["id"] == "reasoning"))
            elif task == "consultation":
                system = prompt_template_dict[f"legal_consultation_{consultation_level}"]
                user = user_prompt_dict["legal_consultation"].format(question=raw["conversation"])
                matches = list(re.finditer(r"(?:^|\n)\s*(\d+)\s*[.、．]\s*[(（]\s*\+\s*(\d+(?:\.\d+)?)\s*分\s*[)）]", raw["rubrics"]))
                if not matches:
                    raise ValueError(f"{sid}: cannot parse consultation rubric allocations")
                rubrics = [{"id": f"q{j+1}", "max_points": float(m[2]),
                            "text": raw["rubrics"][m.start():matches[j+1].start() if j+1 < len(matches) else None].strip()}
                           for j, m in enumerate(matches)]
                if any(int(m[1]) != j+1 for j,m in enumerate(matches)):
                    issues.append({"id":sid,"kind":"consultation_numbering_repaired",
                                   "source_numbers":[int(m[1]) for m in matches],
                                   "policy":"Unique positional IDs; original text and every point allocation preserved"})
                total = re.search(r"总分\s*[:：]\s*(\d+)", raw["rubrics"])
                if total and float(total[1]) != sum(r["max_points"] for r in rubrics):
                    issues.append({"id": sid, "kind": "consultation_total_mismatch", "declared": float(total[1]),
                                   "allocated": sum(r["max_points"] for r in rubrics)})
                group, sequence = consultation_level, "not_applicable"
            else:
                system = prompt_template_dict["document_generation"]
                user = user_prompt_dict["document_generation"].format(question=raw["conversation"])
                rubrics = [{"id": "document", "max_points": float(raw["score"]), "text": raw["Rubrics"]}]
                group, sequence = raw["tag"], "not_applicable"
            if any(r["max_points"] <= 0 for r in rubrics):
                raise ValueError(f"{sid}: nonpositive rubric denominator")
            if len({r['id'] for r in rubrics}) != len(rubrics):
                raise ValueError(f"{sid}: duplicate rubric IDs")
            sample = {"id": sid, "task": task, "domain": group, "sequence": sequence,
                      "source_file": filename, "source_row": index, "source_sha256": digest(raw),
                      "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
                      "rubrics": rubrics, "max_points": sum(r["max_points"] for r in rubrics)}
            if task == "consultation":
                sample["question_limit"] = 25 if consultation_level == "mid" else 50
                sample["question_min"] = 10 if consultation_level == "mid" else 25
            samples.append(sample)
    if len({s["id"] for s in samples}) != len(samples):
        raise ValueError("Duplicate sample ids")
    manifest = {"schema_version": 2, "count": len(samples), "tasks": dict(Counter(s["task"] for s in samples)),
                "domains": dict(Counter(s["domain"] for s in samples if s["task"] == "case_analysis")),
                "sequence": dict(Counter(s["sequence"] for s in samples if s["task"] == "case_analysis")),
                "sources": {f: file_hash(root / f) for f in FILES.values()}, "issues": issues,
                "denominator_policy": "case: structured points; consultation: sum explicit point allocations; drafting: score field",
                "consultation_level": consultation_level, "dataset_sha256": digest(samples)}
    return samples, manifest


def select(samples, per_task=None, tasks=None):
    counts = Counter()
    selected = []
    for s in samples:
        if tasks and s["task"] not in tasks:
            continue
        if per_task is not None and counts[s["task"]] >= per_task:
            continue
        selected.append(s)
        counts[s["task"]] += 1
    if not selected:
        raise ValueError("Selection contains no samples")
    return selected
