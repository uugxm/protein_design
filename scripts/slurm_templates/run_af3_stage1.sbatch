#!/bin/bash
#SBATCH -J af3_stage1
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 16
#SBATCH --mem=64G
#SBATCH --time=08:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CANONICAL_MANIFEST="${CANONICAL_MANIFEST:?Set CANONICAL_MANIFEST=/path/to/canonical_manifest.tsv}"
OUT_ROOT="${OUT_ROOT:-$PWD/af3_stage1}"
AF3_INPUT_DIR="${AF3_INPUT_DIR:-$OUT_ROOT/inputs}"
AF3_STAGE1_DIR="${AF3_STAGE1_DIR:-$OUT_ROOT/raw_stage1}"
AF3_ASSET_DIR="${AF3_ASSET_DIR:-$OUT_ROOT/assets}"
AF3_SIF="${AF3_SIF:-/public/apps/alphafold3/alphafold3/alphafold3.0.1.sif}"
AF3_MODEL_DIR="${AF3_MODEL_DIR:-/public/shared/alphafold3/models}"
AF3_DB_DIR="${AF3_DB_DIR:-/public/shared/alphafold3}"
AF3_BIND="${AF3_BIND:-/public/shared/alphafold3:/public/shared/alphafold3}"
AF3_STAGE1_EXTRA_ARGS="${AF3_STAGE1_EXTRA_ARGS:-}"

mkdir -p logs "$AF3_INPUT_DIR" "$AF3_STAGE1_DIR" "$AF3_ASSET_DIR"
module purge || true

"$PYTHON_BIN" "$BASE/scripts/make_af3_json_inputs.py" \
  --canonical_manifest "$CANONICAL_MANIFEST" \
  --out_dir "$AF3_INPUT_DIR" \
  --manifest "$AF3_INPUT_DIR/manifest.tsv"

apptainer exec --bind "$AF3_BIND" "$AF3_SIF" \
  python /app/alphafold/run_alphafold.py \
    --input_dir "$AF3_INPUT_DIR" \
    --output_dir "$AF3_STAGE1_DIR" \
    --model_dir "$AF3_MODEL_DIR" \
    --db_dir "$AF3_DB_DIR" \
    --run_inference=False \
    $AF3_STAGE1_EXTRA_ARGS

"$PYTHON_BIN" "$BASE/scripts/extract_af3_stage1_assets.py" \
  --input_dir "$AF3_STAGE1_DIR" \
  --out_dir "$AF3_ASSET_DIR" \
  --manifest "$AF3_ASSET_DIR/af3_stage1_asset_manifest.tsv"
