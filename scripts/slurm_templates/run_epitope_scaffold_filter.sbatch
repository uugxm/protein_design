#!/bin/bash
#SBATCH -J epi_filter
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH --time=00:20:00
#SBATCH -o logs/%x-%A_%a.out
#SBATCH -e logs/%x-%A_%a.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python}"
TASK_LIST="${TASK_LIST:-$PWD/backbone_list.txt}"
WORK_ROOT="${WORK_ROOT:-$PWD/array_work}"
REFERENCE_PDB="${REFERENCE_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-1.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"

mkdir -p logs "$WORK_ROOT"
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
hostname

if [ ! -s "$TASK_LIST" ]; then
  echo "Missing TASK_LIST: $TASK_LIST" >&2
  exit 2
fi

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
ITEM="$(sed -n "${TASK_ID}p" "$TASK_LIST")"
if [ -z "$ITEM" ]; then
  echo "No item at line $TASK_ID in $TASK_LIST" >&2
  exit 2
fi

DESIGN_ID="$(basename "$ITEM" .pdb)"
TASK_DIR="$WORK_ROOT/$DESIGN_ID"
TRB_DIR="$TASK_DIR/trb"
PRED_FLAT_DIR="$TASK_DIR/predictions_flat"

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
