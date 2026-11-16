"""Crash-safe stages with immutable configurations and content-addressed inputs."""
from contextlib import contextmanager
from datetime import datetime, timezone
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
import fcntl
import json
import platform
import time

from .io import digest, write_json, append_jsonl
from .scoring import judge_messages, parse_scores, limit_questions


def now():
    return datetime.now(timezone.utc).isoformat()


def environment():
    packages = {}
    for name in ("plawbench", "mlx", "mlx-lm", "transformers", "huggingface-hub", "numpy"):
        try:
            packages[name] = version(name)
        except PackageNotFoundError:
            pass
    return {"system": platform.system(), "release": platform.release(), "machine": platform.machine(),
            "python": platform.python_version(), "packages": packages}


@contextmanager
def run_lock(root):
    root = Path(root)
    root.mkdir(parents=True, exist_ok=True)
    with (root / ".running").open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise ValueError(f"Another process is writing to {root}") from exc
        try:
            yield
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def stage_manifest(root, stage, config, samples, model_info):
    root = Path(root)
    identity = {"config": config, "samples_sha256": digest(samples), "model": model_info}
    fingerprint = digest(identity)
    path = root / f"{stage}_manifest.json"
    from .io import file_hash
    code_hashes = {p.name:file_hash(p) for p in sorted(Path(__file__).parent.glob('*.py'))}
    if path.exists():
        prior = json.loads(path.read_text())
        if prior["fingerprint"] != fingerprint:
            raise ValueError(f"{stage} configuration/data/model changed. Use a new output directory.")
        append_jsonl(root/'resumes.jsonl', {'stage':stage,'time':now(),'fingerprint':fingerprint,
                                          'source_code_sha256':code_hashes})
        return prior
    manifest = {**identity, "fingerprint": fingerprint, "created_at": now(), "environment": environment(),
                "source_code_sha256": code_hashes}
    write_json(path, manifest)
    return manifest


def progress(root, event):
    event = {"time": now(), **event}
    append_jsonl(Path(root) / "events.jsonl", event)
    print(json.dumps(event, ensure_ascii=False), flush=True)


def generate(samples, backend, root, max_tokens=4096, document_max_tokens=6144, temperature=0.0, seed=42, batch_size=1):
    root = Path(root)
    config = {"max_tokens": max_tokens, "document_max_tokens": document_max_tokens,
              "temperature": temperature, "seed": seed, "protocol": "original-generation-v1"}
    if batch_size != 1:
        config["batch_size"] = batch_size
    with run_lock(root):
        manifest = stage_manifest(root, "generation", config, samples, backend.info)
        target = root / "predictions"
        target.mkdir(exist_ok=True)
        pending = []
        for i, sample in enumerate(samples, 1):
            path = target / f"{sample['id']}.json"
            if path.exists():
                old = json.loads(path.read_text())
                if old["fingerprint"] != manifest["fingerprint"] or old["input_sha256"] != digest(sample["messages"]):
                    raise ValueError(f"Stale prediction: {path}")
                if old["response_sha256"] != digest(old["text"]):
                    raise ValueError(f"Prediction integrity mismatch: {path}")
                continue
            pending.append((i, sample))
        for offset in range(0, len(pending), batch_size):
            chunk = pending[offset:offset+batch_size]
            budgets = [document_max_tokens if s["task"] in ("plaintiff", "defendant") else max_tokens for _,s in chunk]
            if batch_size > 1:
                outputs = backend.generate_batch([s["messages"] for _,s in chunk], budgets, temperature, seed + chunk[0][1]["source_row"])
            else:
                outputs = [backend.generate(chunk[0][1]["messages"], budgets[0], temperature, seed + chunk[0][1]["source_row"])]
            for (i, sample), output in zip(chunk, outputs):
                path = target / f"{sample['id']}.json"
                record = {"id": sample["id"], "task": sample["task"], "created_at": now(),
                      "fingerprint": manifest["fingerprint"], "input_sha256": digest(sample["messages"]), **output}
                record["response_sha256"] = digest(output["text"])
                if sample["task"] == "consultation":
                    _, count = limit_questions(output["text"], sample["question_limit"])
                    record["format_check"] = {"numbered_questions": count,
                                          "within_requested_range": sample["question_min"] <= count <= sample["question_limit"]}
                elif sample["task"] in ("plaintiff", "defendant"):
                    chars = len("".join(output["text"].split()))
                    record["format_check"] = {"nonwhitespace_characters": chars, "within_requested_range": 2500 <= chars <= 3000}
                write_json(path, record)
                progress(root, {"stage": "generate", "completed": i, "total": len(samples), "id": sample["id"],
                            "tokens": output["generation_tokens"], "seconds": round(output["elapsed_seconds"], 2),
                            "finish_reason": output["finish_reason"]})
        export_records(root, "predictions", samples)


def judge(samples, backend, root, max_tokens=2048, retries=2, seed=42, retry_failed=False, batch_size=1):
    root = Path(root)
    # Bind grading to the exact responses, rubric and judging instruction, not just sample IDs.
    predictions = {}
    for sample in samples:
        path = root / "predictions" / f"{sample['id']}.json"
        if not path.exists():
            raise ValueError(f"Missing prediction: {sample['id']}; run generate first")
        record = json.loads(path.read_text())
        if record["input_sha256"] != digest(sample["messages"]) or record["response_sha256"] != digest(record["text"]):
            raise ValueError(f"Prediction integrity mismatch: {sample['id']}")
        predictions[sample["id"]] = record
    config = {"max_tokens": max_tokens, "retries": retries, "seed": seed, "protocol": "rubric-json-v2-full-instructions",
              "inputs_sha256": digest([judge_messages(s, predictions[s["id"]]["text"]) for s in samples])}
    if batch_size != 1:
        config["batch_size"] = batch_size
    with run_lock(root):
        manifest = stage_manifest(root, "judge", config, samples, backend.info)
        target = root / "grades"
        target.mkdir(exist_ok=True)
        initial_results = {}
        for i, sample in enumerate(samples, 1):
            path = target / f"{sample['id']}.json"
            if path.exists():
                previous = json.loads(path.read_text())
                if previous["fingerprint"] != manifest["fingerprint"]:
                    raise ValueError(f"Stale grade: {path}")
                if previous["status"] == "ok" or not retry_failed:
                    continue
            messages = judge_messages(sample, predictions[sample["id"]]["text"])
            if batch_size > 1 and sample["id"] not in initial_results:
                chunk = []
                for candidate in samples[i-1:]:
                    candidate_path = target / f"{candidate['id']}.json"
                    if candidate_path.exists():
                        old = json.loads(candidate_path.read_text())
                        if old['status'] == 'ok' or not retry_failed:
                            continue
                    chunk.append(candidate)
                    if len(chunk) == batch_size:
                        break
                outputs = backend.generate_batch([judge_messages(s, predictions[s['id']]['text']) for s in chunk],
                                                 [max_tokens]*len(chunk), 0.0, seed + sample['source_row'])
                initial_results.update({s['id']: o for s,o in zip(chunk, outputs)})
            history = previous.get("attempts", []) if path.exists() else []
            record = {"id": sample["id"], "task": sample["task"], "created_at": now(), "status": "failed",
                      "fingerprint": manifest["fingerprint"], "response_sha256": predictions[sample["id"]]["response_sha256"],
                      "attempts": history}
            if path.exists() and previous.get('inherited_attempts'):
                record['inherited_attempts'] = previous['inherited_attempts']
            for attempt in range(retries + 1):
                if attempt == 0 and sample['id'] in initial_results:
                    output = initial_results.pop(sample['id'])
                else:
                    output = backend.generate(messages, max_tokens, 0.0 if attempt == 0 else 0.2,
                                              seed + sample["source_row"] + len(history))
                entry = {**output, "attempt": len(history) + 1}
                try:
                    if output["finish_reason"] == "length":
                        raise ValueError("Judge output reached its token budget")
                    scores = parse_scores(output["text"], sample["rubrics"])
                    record.update(status="ok", scores=scores, points=sum(s["points"] for s in scores),
                                  max_points=sample["max_points"])
                except ValueError as exc:
                    entry["error"] = str(exc)
                history.append(entry)
                write_json(path, record)
                if record["status"] == "ok":
                    break
                # Resend the same rubric; never include a model-fabricated denominator.
                messages = judge_messages(sample, predictions[sample["id"]]["text"])
                messages.append({"role": "user", "content": f"上次输出验证失败：{entry['error']}。请重新输出完整JSON并核对所有id和分数范围。"})
            progress(root, {"stage": "judge", "completed": i, "total": len(samples),
                            "id": sample["id"], "status": record["status"], "attempts": len(history)})
        export_records(root, "grades", samples)


def export_records(root, folder, samples):
    root = Path(root)
    records = [json.loads((root / folder / f"{s['id']}.json").read_text()) for s in samples
               if (root / folder / f"{s['id']}.json").exists()]
    path = root / f"{folder}.jsonl"
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    tmp.replace(path)
    return records
