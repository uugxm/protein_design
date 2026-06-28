#!/bin/bash
#SBATCH -J af3_infer
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
AF3_DATA_INPUT_DIR="${AF3_DATA_INPUT_DIR:?Set AF3_DATA_INPUT_DIR to AF3 Stage 1 output containing *_data.json files}"
PRED_DIR="${PRED_DIR:-$PWD/af3_predictions}"
PRED_FLAT_DIR="${PRED_FLAT_DIR:-$PWD/predictions_flat/af3}"
AF3_SIF="${AF3_SIF:-/public/apps/alphafold3/alphafold3/alphafold3.0.1.sif}"
AF3_MODEL_DIR="${AF3_MODEL_DIR:-/public/shared/alphafold3/models}"
AF3_DB_DIR="${AF3_DB_DIR:-/public/shared/alphafold3}"
AF3_BIND="${AF3_BIND:-/public/shared/alphafold3:/public/shared/alphafold3}"
AF3_INFERENCE_EXTRA_ARGS="${AF3_INFERENCE_EXTRA_ARGS:-}"

mkdir -p logs "$PRED_DIR" "$PRED_FLAT_DIR"
module purge || true
module load cuda/12.4 || true
nvidia-smi -L

apptainer exec --nv --bind "$AF3_BIND" "$AF3_SIF" \
  python /app/alphafold/run_alphafold.py \
    --input_dir "$AF3_DATA_INPUT_DIR" \
    --output_dir "$PRED_DIR" \
    --model_dir "$AF3_MODEL_DIR" \
    --db_dir "$AF3_DB_DIR" \
    --run_data_pipeline=False \
    $AF3_INFERENCE_EXTRA_ARGS

"$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
  --predictor af3 \
  --input_dir "$PRED_DIR" \
  --out_dir "$PRED_FLAT_DIR" \
  --design_id "$DESIGN_ID"
