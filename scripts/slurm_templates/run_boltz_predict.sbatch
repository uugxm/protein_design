#!/bin/bash
#SBATCH -J boltz_predict
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
DESIGN_ID="${DESIGN_ID:-prediction_batch}"
CANONICAL_MANIFEST="${CANONICAL_MANIFEST:?Set CANONICAL_MANIFEST=/path/to/canonical_manifest.tsv}"
AF3_STAGE1_ASSET_MANIFEST="${AF3_STAGE1_ASSET_MANIFEST:-}"
BOLTZ_INPUT_DIR="${BOLTZ_INPUT_DIR:-$PWD/prediction_inputs/boltz}"
PRED_DIR="${PRED_DIR:-$PWD/predictions_boltz}"
PRED_FLAT_DIR="${PRED_FLAT_DIR:-$PWD/predictions_flat/boltz}"
BOLTZ_ENV="${BOLTZ_ENV:-$BASE/envs/boltz}"
BOLTZ_CACHE="${BOLTZ_CACHE:-$BASE/weights/boltz}"
BOLTZ_CMD="${BOLTZ_CMD:-boltz}"
BOLTZ_EXTRA_ARGS="${BOLTZ_EXTRA_ARGS:-}"

mkdir -p logs "$BOLTZ_INPUT_DIR" "$PRED_DIR" "$PRED_FLAT_DIR" "$BOLTZ_CACHE"
module purge || true
module load cuda/12.4 || true
if [ -d "$BOLTZ_ENV/bin" ]; then
  export PATH="$BOLTZ_ENV/bin:$PATH"
fi
export BOLTZ_CACHE
nvidia-smi -L

ADAPTER_ARGS=(--canonical_manifest "$CANONICAL_MANIFEST" --out_dir "$BOLTZ_INPUT_DIR" --manifest "$BOLTZ_INPUT_DIR/manifest.tsv")
if [ -n "$AF3_STAGE1_ASSET_MANIFEST" ]; then
  ADAPTER_ARGS+=(--af3_stage1_manifest "$AF3_STAGE1_ASSET_MANIFEST")
fi
"$PYTHON_BIN" "$BASE/scripts/make_boltz_inputs.py" "${ADAPTER_ARGS[@]}"

"$BOLTZ_CMD" predict "$BOLTZ_INPUT_DIR" --out_dir "$PRED_DIR" --cache "$BOLTZ_CACHE" $BOLTZ_EXTRA_ARGS

"$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
  --predictor boltz \
  --input_dir "$PRED_DIR" \
  --out_dir "$PRED_FLAT_DIR" \
  --design_id "$DESIGN_ID"
