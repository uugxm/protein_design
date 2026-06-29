#!/bin/bash
#SBATCH -J rf3_confirm
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=32G
#SBATCH --time=04:00:00
#SBATCH -o logs/%x-%A_%a.out
#SBATCH -e logs/%x-%A_%a.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
TASK_TSV="${TASK_TSV:?Set TASK_TSV to RF3 confirmation task TSV}"
WORK_ROOT="${WORK_ROOT:-$PWD/rf3_confirmations}"
REFERENCE_PDB="${REFERENCE_PDB:?Set REFERENCE_PDB}"
MOTIF_TSV="${MOTIF_TSV:?Set MOTIF_TSV}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"
FOUNDRY_ENV="${FOUNDRY_ENV:-$BASE/envs/foundry-rfd3}"
FOUNDRY_CHECKPOINT_DIRS="${FOUNDRY_CHECKPOINT_DIRS:-$BASE/weights/foundry}"
RF3_CKPT_PATH="${RF3_CKPT_PATH:-$FOUNDRY_CHECKPOINT_DIRS/rf3_foundry_01_24_latest_remapped.ckpt}"
RF3_CMD="${RF3_CMD:-rf3}"
RF3_EXTRA_ARGS="${RF3_EXTRA_ARGS:-}"

mkdir -p logs "$WORK_ROOT"
module purge || true
module load cuda/12.4 || true
if [ -d "$FOUNDRY_ENV/bin" ]; then
  export PATH="$FOUNDRY_ENV/bin:$PATH"
fi
export FOUNDRY_CHECKPOINT_DIRS
nvidia-smi -L

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
LINE="$(awk -F '\t' -v n="$((TASK_ID + 1))" 'NR==n {print}' "$TASK_TSV")"
if [ -z "$LINE" ]; then
  echo "No RF3 task at array index $TASK_ID in $TASK_TSV" >&2
  exit 2
fi

IFS=$'\t' read -r DESIGN_ID CANONICAL_MANIFEST BACKBONE_PDB TRB_PATH _REST <<< "$LINE"
if [ ! -s "$CANONICAL_MANIFEST" ]; then
  echo "Missing canonical manifest: $CANONICAL_MANIFEST" >&2
  exit 2
fi
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

TASK_DIR="$WORK_ROOT/$DESIGN_ID"
RF3_INPUT_DIR="$TASK_DIR/prediction_inputs/rf3"
PRED_DIR="$TASK_DIR/rf3_predictions"
PRED_FLAT_DIR="$TASK_DIR/predictions_flat/rf3"
TRB_DIR="$TASK_DIR/trb"
mkdir -p "$RF3_INPUT_DIR" "$PRED_DIR" "$PRED_FLAT_DIR" "$TRB_DIR"
if [ -s "$TRB_PATH" ]; then
  ln -sfn "$TRB_PATH" "$TRB_DIR/$DESIGN_ID.trb"
fi

"$PYTHON_BIN" "$BASE/scripts/make_rf3_json_inputs.py" \
  --canonical_manifest "$CANONICAL_MANIFEST" \
  --out_dir "$RF3_INPUT_DIR" \
  --manifest "$RF3_INPUT_DIR/manifest.tsv"

"$RF3_CMD" fold inputs="$RF3_INPUT_DIR" out_dir="$PRED_DIR" ckpt_path="$RF3_CKPT_PATH" $RF3_EXTRA_ARGS

"$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
  --predictor rf3 \
  --input_dir "$PRED_DIR" \
  --out_dir "$PRED_FLAT_DIR" \
  --design_id "$DESIGN_ID"

"$PYTHON_BIN" "$BASE/scripts/filter_designs.py" \
  --input_dir "$PRED_FLAT_DIR" \
  --pdb_dir "$PRED_FLAT_DIR" \
  --reference_pdb "$REFERENCE_PDB" \
  --motif_tsv "$MOTIF_TSV" \
  --trb_dir "$TRB_DIR" \
  --min_plddt "$MIN_PLDDT" \
  --max_pae "$MAX_PAE" \
  --max_motif_rmsd "$MAX_MOTIF_RMSD" \
  --max_clashes "$MAX_CLASHES" \
  --output_csv "$TASK_DIR/filter_summary.csv"
