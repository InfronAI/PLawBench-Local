# Preliminary Qwen3 pipeline check

Four real generations and four real judgments cover one example of each public
subset. The candidate and judge are the pinned local Qwen3-4B model.

This run predates the final judge protocol: its judge saw the scenario, answer
and rubric, but did not receive the complete generation instructions. Do not
compare these scores directly with `m1-public`, which uses the expanded context.

`judge_audit.json` records a manually confirmed evidence-grounding error:
the judge claimed that the answer cited three article numbers which are absent
from that answer. `judge_evidence_audit.json` records the automated lexical
screen. Neither artifact changes the scores or verifies the legal content.

The current artifact verifier revalidates source maxima, responses, scores and
all summary fields. Its `judge_prompt_hash_verified: false` means that it does
not reconstruct the legacy v1 prompt; it reconstructs prompt hashes only for
the v2 protocol used in the complete public run.
