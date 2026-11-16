"""CLI for explicit, independently resumable experiment stages."""
import argparse
import gc
import json
from pathlib import Path
import sys

from .data import load_dataset, select, FILES
from .io import write_json

MODEL = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
JUDGE = "mlx-community/Qwen3-4B-Instruct-2507-4bit"


def parser():
    p = argparse.ArgumentParser(prog="plawbench", description=__doc__)
    sub = p.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="Inspect Python, Apple GPU and installed dependencies")
    for name in ("prepare", "generate", "judge", "run", "report"):
        q = sub.add_parser(name)
        q.add_argument("--data-dir", type=Path)
        q.add_argument("--output", type=Path, default=Path("experiments/local"))
        q.add_argument("--per-task", type=int, help="First N rows of each subset; omit to run all 280")
        q.add_argument("--tasks", nargs="+", choices=list(FILES))
        q.add_argument("--consultation-level", choices=["mid", "hard"], default="mid")
        if name in ("generate", "judge", "run"):
            q.add_argument("--model", default=MODEL)
            q.add_argument("--model-revision")
            q.add_argument("--judge-model", default=JUDGE)
            q.add_argument("--judge-revision")
            q.add_argument("--offline", action="store_true", help="Use cached model snapshots only")
            q.add_argument("--max-tokens", type=int, default=4096)
            q.add_argument("--document-max-tokens", type=int, default=6144)
            q.add_argument("--judge-max-tokens", type=int, default=2048)
            q.add_argument("--temperature", type=float, default=0.0)
            q.add_argument("--seed", type=int, default=42)
            q.add_argument("--retries", type=int, default=2)
            q.add_argument("--batch-size", type=int, default=1, help="Bounded generation batch size (1–4 on 16 GB M1)")
            q.add_argument("--judge-batch-size", type=int, help="Separate judge batch size; defaults to --batch-size")
            q.add_argument("--retry-failed", action="store_true")
    q = sub.add_parser("calibrate", help="Compare imported human and judge scores by sample id")
    q.add_argument("--human", type=Path, required=True)
    q.add_argument("--judge", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q = sub.add_parser("pilot", help="Prepare stratified samples and blank three-expert rating forms")
    q.add_argument("--run", type=Path, required=True)
    q.add_argument("--output", type=Path, required=True)
    q.add_argument("--seed", type=int, default=42)
    return p


def main(argv=None):
    args = parser().parse_args(argv)
    try:
        if args.command == "doctor":
            from .pipeline import environment
            info = environment()
            try:
                import mlx.core as mx
                info["metal_available"] = mx.metal.is_available()
                info["device"] = mx.device_info()
            except ImportError:
                info["metal_available"] = False
            print(json.dumps(info, indent=2))
            return
        if args.command == "calibrate":
            from .analysis import calibrate
            write_json(args.output, calibrate(args.human, args.judge))
            return
        if args.command == 'pilot':
            from .pilot import export_pilot
            print(json.dumps(export_pilot(args.run,args.output,args.seed),ensure_ascii=False,indent=2))
            return
        if args.per_task is not None and args.per_task <= 0:
            raise ValueError("--per-task must be positive")
        for key in ("max_tokens", "document_max_tokens", "judge_max_tokens"):
            if hasattr(args, key) and getattr(args, key) <= 0:
                raise ValueError(f"--{key.replace('_', '-')} must be positive")
        if hasattr(args, "retries") and args.retries < 0:
            raise ValueError("--retries must be nonnegative")
        if hasattr(args, "batch_size") and not 1 <= args.batch_size <= 4:
            raise ValueError("--batch-size must be between 1 and 4")
        if getattr(args,'judge_batch_size',None) is not None and not 1 <= args.judge_batch_size <= 4:
            raise ValueError("--judge-batch-size must be between 1 and 4")
        samples, manifest = load_dataset(args.data_dir, args.consultation_level)
        samples = select(samples, args.per_task, args.tasks)
        args.output.mkdir(parents=True, exist_ok=True)
        if args.command == "prepare":
            from .pipeline import run_lock
            from .io import digest
            with run_lock(args.output):
                path = args.output / "samples.json"
                if path.exists() and digest(json.loads(path.read_text())) != digest(samples):
                    raise ValueError("Output directory already contains a different sample selection")
                write_json(args.output / "dataset_manifest.json", manifest)
                write_json(path, samples)
            print(json.dumps({"selected": len(samples), "manifest": manifest}, ensure_ascii=False, indent=2))
            return
        from .pipeline import generate, judge, run_lock
        # Dataset metadata is immutable once a run starts.
        from .io import digest
        with run_lock(args.output):
            selected_path = args.output / "samples.json"
            if selected_path.exists() and digest(json.loads(selected_path.read_text())) != digest(samples):
                raise ValueError("Output directory contains a different sample selection")
            if not selected_path.exists():
                write_json(selected_path, samples)
                write_json(args.output / "dataset_manifest.json", manifest)
        if args.command in ("generate", "run"):
            from .backends import MLXBackend
            model = MLXBackend(args.model, args.model_revision, args.offline)
            generate(samples, model, args.output, args.max_tokens, args.document_max_tokens,
                     args.temperature, args.seed, args.batch_size)
            reuse_model = (args.command == 'run' and args.model == args.judge_model
                           and args.model_revision == args.judge_revision)
            if not reuse_model:
                del model
                gc.collect()
        if args.command in ("judge", "run"):
            from .backends import MLXBackend
            if args.command == 'judge' or not reuse_model:
                model = MLXBackend(args.judge_model, args.judge_revision, args.offline)
            judge(samples, model, args.output, args.judge_max_tokens, args.retries, args.seed, args.retry_failed,
                  args.judge_batch_size or args.batch_size)
            del model
            gc.collect()
        if args.command in ("report", "run"):
            from .analysis import report
            summary = report(samples, args.output)
            print(json.dumps(summary["coverage"], ensure_ascii=False, indent=2))
            if summary["coverage"]["graded"] != len(samples):
                raise ValueError("Report saved, but grading is incomplete; inspect failures and resume")
    except (ValueError, RuntimeError, OSError, ImportError) as exc:
        print(f"plawbench: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
