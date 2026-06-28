#!/bin/bash
#SBATCH -J rf3_predict
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
RF3_INPUT_DIR="${RF3_INPUT_DIR:-$PWD/prediction_inputs/rf3}"
PRED_DIR="${PRED_DIR:-$PWD/rf3_predictions}"
PRED_FLAT_DIR="${PRED_FLAT_DIR:-$PWD/predictions_flat/rf3}"
FOUNDRY_ENV="${FOUNDRY_ENV:-$BASE/envs/foundry-rfd3}"
FOUNDRY_CHECKPOINT_DIRS="${FOUNDRY_CHECKPOINT_DIRS:-$BASE/weights/foundry}"
RF3_CKPT_PATH="${RF3_CKPT_PATH:-$FOUNDRY_CHECKPOINT_DIRS/rf3_foundry_01_24_latest_remapped.ckpt}"
RF3_CMD="${RF3_CMD:-rf3}"
RF3_EXTRA_ARGS="${RF3_EXTRA_ARGS:-}"

mkdir -p logs "$RF3_INPUT_DIR" "$PRED_DIR" "$PRED_FLAT_DIR"
module purge || true
module load cuda/12.4 || true
if [ -d "$FOUNDRY_ENV/bin" ]; then
  export PATH="$FOUNDRY_ENV/bin:$PATH"
fi
export FOUNDRY_CHECKPOINT_DIRS
nvidia-smi -L
if [ ! -s "$RF3_CKPT_PATH" ]; then
  echo "Missing RF3 checkpoint: $RF3_CKPT_PATH" >&2
  exit 2
fi
case " $RF3_EXTRA_ARGS " in
  *diffusion_batch_size*|*n_batches*|*inference_sampler.num_timesteps*)
    echo "RF3 fold cannot accept RFD3 design overrides in RF3_EXTRA_ARGS: $RF3_EXTRA_ARGS" >&2
    exit 2
    ;;
esac

ADAPTER_ARGS=(--canonical_manifest "$CANONICAL_MANIFEST" --out_dir "$RF3_INPUT_DIR" --manifest "$RF3_INPUT_DIR/manifest.tsv")
if [ -n "$AF3_STAGE1_ASSET_MANIFEST" ]; then
  ADAPTER_ARGS+=(--af3_stage1_manifest "$AF3_STAGE1_ASSET_MANIFEST")
fi
"$PYTHON_BIN" "$BASE/scripts/make_rf3_json_inputs.py" "${ADAPTER_ARGS[@]}"

"$RF3_CMD" fold inputs="$RF3_INPUT_DIR" out_dir="$PRED_DIR" ckpt_path="$RF3_CKPT_PATH" $RF3_EXTRA_ARGS

"$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
  --predictor rf3 \
  --input_dir "$PRED_DIR" \
  --out_dir "$PRED_FLAT_DIR" \
  --design_id "$DESIGN_ID"
