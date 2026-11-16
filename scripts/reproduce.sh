#!/bin/sh
set -eu
cd "$(dirname "$0")/.."
PYTHON="${PLAWBENCH_PYTHON:-.venv/bin/python}"
"$PYTHON" -m plawbench doctor
"$PYTHON" -m plawbench run \
  --model mlx-community/Qwen3-4B-Instruct-2507-4bit \
  --model-revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b \
  --judge-model mlx-community/Qwen3-4B-Instruct-2507-4bit \
  --judge-revision 50d427756c6b1b2fe0c0a10f67fbda1fc8e82c1b \
  --max-tokens 16384 --document-max-tokens 16384 --judge-max-tokens 2048 \
  --batch-size 4 --judge-batch-size 2 --seed 42 --output "${PLAWBENCH_OUTPUT:-experiments/m1-public}" "$@"
