# M1 implementation and measurement notes

The verified machine is an Apple M1 Pro with 16 GB unified memory, macOS 26, and native Python 3.11.16. `experiments/validation/environment.json` records the Metal device and dependency versions without hardware serial numbers. The installed MLX 0.32.4 and mlx-metal 0.32.4 wheel tags are `macosx_26_0_arm64`; the pinned installation therefore requires macOS 26 or newer. Older macOS configurations are not validated.

- The core package uses only the Python standard library. MLX imports occur only when a model is requested.
- Four-bit weights avoid CUDA and large full-precision tensors. Only one model instance is resident during the canonical candidate/self-judge run.
- MLX free allocator cache is capped at 128 MiB. The memory allocation guideline is min(6 GiB, 45% of physical RAM), with active allocation checks every 128 decode steps. This is not a strict bound on transient peak memory during prompt evaluation.
- At most four sequences decode together. Prompt prefill is one sequence at a time in 512-token chunks. Smaller batches are available; different batches can produce different greedy output due to numerical rounding.
- Generation and judgment results are persisted atomically per sample after a bounded batch completes. An interrupted unfinished batch can be recomputed; committed records are verified before reuse. A file lock excludes simultaneous writers to the same run.
- A model's immutable snapshot ID and actual files are hashed, including the separate Jinja chat template used by Qwen3. First-time downloads include that template; there is no dependency on a pre-populated local cache.

## Recorded investigations

The initial unrestricted-cache four-way attempt was stopped before any answer checkpoint completed. A process sample recorded an 11.5 GB **physical footprint peak** while the host had substantial existing swap usage. The aborted attempt is retained in `experiments/m1-batch4-aborted/`.

After applying cache and allocation controls, a two-question batch completed with a 3.40 GB **MLX allocator peak** in `experiments/m1-batch2-check/`. The full experiment uses four-way batches and reports its own measured peak. These are different batch sizes and memory instruments, not a controlled before/after speed or memory-reduction claim. Host contention also affects timings.

MLX token-generation throughput excludes prompt prefill. The report's end-to-end token rate includes generation-stage prefill time. Batch wall time is divided across its records for additive accounting; actual completion latency is saved separately. Model download, load and hashing time is outside per-response timing. Wall-clock event timestamps and the run log retain the execution chronology.

Read-only host memory snapshots are saved in `experiments/validation/host_memory_observations.jsonl`. At 2026-11-15 12:51 UTC, macOS reported 22,153.75 MiB of system-wide swap in use. This is a shared-host observation, not the benchmark's own allocation or proof of the cause of changing batch times. No other applications were stopped to improve the measurements.
