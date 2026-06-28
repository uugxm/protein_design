#!/bin/bash
#SBATCH -J foundry_rfd3_smoke
#SBATCH -p Interactive
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=48G
#SBATCH --time=02:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
RUN_ROOT="${RUN_ROOT:-$BASE/examples/epitope_scaffold/foundry_rfd3_official_smoke_$(date +%Y%m%d_%H%M%S)}"
FOUNDRY_REPO="${FOUNDRY_REPO:-$BASE/repos/foundry}"
FOUNDRY_ENV_PREFIX="${FOUNDRY_ENV_PREFIX:-$BASE/envs/foundry-rfd3}"
FOUNDRY_CHECKPOINT_DIR="${FOUNDRY_CHECKPOINT_DIR:-$BASE/weights/foundry}"
FOUNDRY_RFD3_TIMESTEPS="${FOUNDRY_RFD3_TIMESTEPS:-20}"

mkdir -p "$RUN_ROOT/logs" "$RUN_ROOT/raw_outputs"

module purge || true
hostname
nvidia-smi -L

"$FOUNDRY_ENV_PREFIX/bin/python" - <<'PY'
import torch
print(f"torch={torch.__version__}")
print(f"cuda_available={torch.cuda.is_available()}")
print(f"cuda_device_count={torch.cuda.device_count()}")
if torch.cuda.is_available():
    print(f"cuda_device_name={torch.cuda.get_device_name(0)}")
PY

FOUNDRY_CHECKPOINT_DIRS="$FOUNDRY_CHECKPOINT_DIR" \
  "$FOUNDRY_ENV_PREFIX/bin/foundry" list-installed

cd "$FOUNDRY_REPO/models/rfd3/docs/examples"
FOUNDRY_CHECKPOINT_DIRS="$FOUNDRY_CHECKPOINT_DIR" \
  "$FOUNDRY_ENV_PREFIX/bin/rfd3" design \
    out_dir="$RUN_ROOT/raw_outputs" \
    inputs=demo.json \
    skip_existing=False \
    prevalidate_inputs=True \
    dump_trajectories=False \
    diffusion_batch_size=1 \
    n_batches=1 \
    inference_sampler.num_timesteps="$FOUNDRY_RFD3_TIMESTEPS" \
    low_memory_mode=True

find "$RUN_ROOT/raw_outputs" -type f | sort > "$RUN_ROOT/output_files.txt"
structure_count="$(grep -Ec '\.(cif|cif\.gz|pdb|pdb\.gz)$' "$RUN_ROOT/output_files.txt" || true)"
if [ "$structure_count" -lt 1 ]; then
  echo "No Foundry RFD3 structure outputs found in $RUN_ROOT/raw_outputs" >&2
  exit 2
fi

cat > "$RUN_ROOT/run_params.env" <<EOF
PROTEIN_DESIGN_HOME=$BASE
FOUNDRY_REPO=$FOUNDRY_REPO
FOUNDRY_ENV_PREFIX=$FOUNDRY_ENV_PREFIX
FOUNDRY_CHECKPOINT_DIR=$FOUNDRY_CHECKPOINT_DIR
FOUNDRY_RFD3_TIMESTEPS=$FOUNDRY_RFD3_TIMESTEPS
RUN_ROOT=$RUN_ROOT
EOF

printf "RUN_ROOT=%s\n" "$RUN_ROOT"
printf "structure_outputs=%s\n" "$structure_count"
