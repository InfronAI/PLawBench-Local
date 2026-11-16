"""Native MLX generation; model loading is deferred until actual inference."""
import platform
import time
from pathlib import Path
from .io import file_hash


class MLXBackend:
    def __init__(self, model, revision=None, offline=False):
        if platform.system() != "Darwin" or platform.machine() != "arm64":
            raise RuntimeError("MLX requires native arm64 Python on Apple Silicon. Data preparation and saved-result analysis work without MLX.")
        import mlx.core as mx
        from mlx_lm import load
        from huggingface_hub import snapshot_download
        if not mx.metal.is_available():
            raise RuntimeError("Apple Metal GPU is unavailable")
        # MLX's default allocator cache can crowd out macOS on 16 GB M1 systems.
        self.memory_limit = min(6 * 1024**3, int(mx.device_info()['memory_size'] * .45))
        mx.set_memory_limit(self.memory_limit)
        mx.set_cache_limit(128 * 1024**2)
        path = Path(model)
        if not path.is_dir():
            path = Path(snapshot_download(model, revision=revision, local_files_only=offline,
                                         allow_patterns=["*.json", "*.safetensors", "*.model", "*.tiktoken", "*.jinja", "*.txt", "*.md"]))
        self.model, self.tokenizer = load(str(path))
        self.info = {"backend": "mlx", "model": model,
                     "memory_limit_bytes": self.memory_limit, "cache_limit_bytes": 128 * 1024**2,
                     "resolved_revision": path.name if path.parent.name == "snapshots" else None,
                     "files": {p.name: file_hash(p) for p in sorted(path.iterdir()) if p.is_file()}}

    def generate(self, messages, max_tokens, temperature=0.0, seed=42):
        import mlx.core as mx
        from mlx_lm import stream_generate
        from mlx_lm.sample_utils import make_sampler
        mx.random.seed(seed)
        prompt = self.tokenizer.apply_chat_template(messages, tokenize=True, add_generation_prompt=True)
        start = time.monotonic()
        text = ""
        last = None
        for last in stream_generate(self.model, self.tokenizer, prompt, max_tokens=max_tokens,
                                    sampler=make_sampler(temp=temperature)):
            text += last.text
            if last.generation_tokens % 128 == 0 and mx.get_active_memory() > self.memory_limit:
                raise RuntimeError("MLX active memory exceeded budget; use batch size 1 or a smaller model in a new run")
        if last is None or not text.strip():
            raise RuntimeError("Model returned an empty response")
        result = {"text": text, "prompt_tokens": last.prompt_tokens,
                  "generation_tokens": last.generation_tokens, "elapsed_seconds": time.monotonic() - start,
                  "tokens_per_second": last.generation_tps, "peak_memory_gb": last.peak_memory,
                  "finish_reason": last.finish_reason or ("length" if last.generation_tokens >= max_tokens else "stop")}
        mx.clear_cache()
        return result

    def generate_batch(self, message_batch, budgets, temperature=0.0, seed=42):
        """Bounded Metal batching. Exact stop reasons and tokens survive batching."""
        import mlx.core as mx
        from mlx_lm.generate import BatchGenerator
        from mlx_lm.sample_utils import make_sampler
        mx.random.seed(seed)
        prompts = [self.tokenizer.apply_chat_template(m, tokenize=True, add_generation_prompt=True)
                   for m in message_batch]
        gen = BatchGenerator(self.model, stop_tokens=self.tokenizer.eos_token_ids,
                             sampler=make_sampler(temp=temperature),
                             completion_batch_size=len(prompts), prefill_batch_size=1,
                             prefill_step_size=512)
        mx.set_wired_limit(self.memory_limit)
        start = time.monotonic()
        uids = gen.insert(prompts, max_tokens=budgets)
        tokens = {uid: [] for uid in uids}
        endings, latency = {}, {}
        steps = 0
        try:
            while responses := gen.next():
                steps += 1
                if steps % 128 == 0 and mx.get_active_memory() > self.memory_limit:
                    raise RuntimeError("MLX active memory exceeded budget; reduce batch size in a new run")
                for response in responses:
                    if response.finish_reason != "stop":
                        tokens[response.uid].append(response.token)
                    if response.finish_reason:
                        endings[response.uid] = response.finish_reason
                        latency[response.uid] = time.monotonic() - start
        finally:
            gen.close()
        elapsed = time.monotonic() - start
        stats = gen.stats()
        outputs = []
        for i, uid in enumerate(uids):
            text = self.tokenizer.decode(tokens[uid])
            if not text.strip() or uid not in endings:
                raise RuntimeError("Batch returned an empty or unfinished response")
            outputs.append({"text": text, "prompt_tokens": len(prompts[i]), "generation_tokens": len(tokens[uid]),
                            "elapsed_seconds": elapsed / len(uids), "completion_latency_seconds": latency[uid],
                            "batch_wall_seconds": elapsed, "batch_size": len(uids),
                            "tokens_per_second": stats.generation_tps, "peak_memory_gb": stats.peak_memory,
                            "finish_reason": endings[uid]})
        del gen
        mx.clear_cache()
        return outputs
