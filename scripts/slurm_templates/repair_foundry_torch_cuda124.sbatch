#!/bin/bash
#SBATCH -J foundry_torch_fix
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
FOUNDRY_ENV_PREFIX="${FOUNDRY_ENV_PREFIX:-$BASE/envs/foundry-rfd3}"
TORCH_VERSION="${TORCH_VERSION:-2.6.0}"
PYTORCH_INDEX_URL="${PYTORCH_INDEX_URL:-https://download.pytorch.org/whl/cu124}"

mkdir -p "$BASE/logs"

"$FOUNDRY_ENV_PREFIX/bin/python" -m pip install --force-reinstall --no-cache-dir \
  --index-url "$PYTORCH_INDEX_URL" \
  "torch==$TORCH_VERSION"

"$FOUNDRY_ENV_PREFIX/bin/python" - <<'PY'
import importlib.metadata as metadata
import torch

print(f"python_torch={torch.__version__}")
print(f"torch_cuda_runtime={torch.version.cuda}")
print(f"rc_foundry={metadata.version('rc-foundry')}")
print(f"torchmetrics={metadata.version('torchmetrics')}")
PY

"$FOUNDRY_ENV_PREFIX/bin/python" -m pip check
