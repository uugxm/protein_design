#!/bin/bash
#SBATCH -J proteinmpnn
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=16G
#SBATCH --time=01:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail
BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
MPNN_REPO="${MPNN_REPO:-$BASE/repos/ProteinMPNN}"
PYTHON_BIN="${PYTHON_BIN:-python}"
PDB_DIR="${PDB_DIR:-$PWD/backbones}"
OUT_DIR="${OUT_DIR:-$PWD/mpnn_outputs}"
MOTIF_TSV="${MOTIF_TSV:-}"
TRB_DIR="${TRB_DIR:-$PDB_DIR}"
FIXED_POSITIONS_JSONL="${FIXED_POSITIONS_JSONL:-$OUT_DIR/fixed_positions.jsonl}"
NUM_SEQ="${NUM_SEQ:-4}"
TEMP="${TEMP:-0.1}"

mkdir -p logs "$OUT_DIR"
hostname
nvidia-smi -L || true
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true

cd "$MPNN_REPO"
"$PYTHON_BIN" helper_scripts/parse_multiple_chains.py \
  --input_path="$PDB_DIR" \
  --output_path="$OUT_DIR/parsed_pdbs.jsonl"

MPNN_EXTRA_ARGS=()
if [ -n "$MOTIF_TSV" ] && [ -s "$MOTIF_TSV" ]; then
  "$PYTHON_BIN" "$BASE/scripts/make_fixed_positions_jsonl.py" \
    --pdb_dir "$PDB_DIR" \
    --motif_tsv "$MOTIF_TSV" \
    --trb_dir "$TRB_DIR" \
    --output_jsonl "$FIXED_POSITIONS_JSONL" \
    --strict
  MPNN_EXTRA_ARGS+=(--fixed_positions_jsonl "$FIXED_POSITIONS_JSONL")
elif [ -s "$FIXED_POSITIONS_JSONL" ]; then
  MPNN_EXTRA_ARGS+=(--fixed_positions_jsonl "$FIXED_POSITIONS_JSONL")
fi

"$PYTHON_BIN" protein_mpnn_run.py \
  --jsonl_path "$OUT_DIR/parsed_pdbs.jsonl" \
  --out_folder "$OUT_DIR" \
  --num_seq_per_target "$NUM_SEQ" \
  --sampling_temp "$TEMP" \
  --seed 37 \
  --batch_size 1 \
  "${MPNN_EXTRA_ARGS[@]}"
