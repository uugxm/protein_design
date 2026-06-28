#!/bin/bash
#SBATCH -J epi_array
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH -o logs/%x-%A_%a.out
#SBATCH -e logs/%x-%A_%a.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python}"
STAGE="${STAGE:-mpnn}"
TASK_LIST="${TASK_LIST:-$PWD/backbone_list.txt}"
WORK_ROOT="${WORK_ROOT:-$PWD/array_work}"
REFERENCE_PDB="${REFERENCE_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
NUM_SEQ="${NUM_SEQ:-4}"
TEMP="${TEMP:-0.1}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-1.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"

mkdir -p logs "$WORK_ROOT"
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
hostname
nvidia-smi -L || true

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
BACKBONE_DIR="$TASK_DIR/backbones"
TRB_DIR="$TASK_DIR/trb"
MPNN_DIR="$TASK_DIR/mpnn_outputs"
PRED_DIR="$TASK_DIR/predictions"
mkdir -p "$BACKBONE_DIR" "$TRB_DIR" "$MPNN_DIR" "$PRED_DIR"
ln -sfn "$ITEM" "$BACKBONE_DIR/$DESIGN_ID.pdb"
if [ -s "${ITEM%.pdb}.trb" ]; then
  ln -sfn "${ITEM%.pdb}.trb" "$TRB_DIR/$DESIGN_ID.trb"
fi

case "$STAGE" in
  mpnn)
    "$PYTHON_BIN" "$BASE/repos/ProteinMPNN/helper_scripts/parse_multiple_chains.py" \
      --input_path "$BACKBONE_DIR" \
      --output_path "$MPNN_DIR/parsed_pdbs.jsonl"
    "$PYTHON_BIN" "$BASE/scripts/make_fixed_positions_jsonl.py" \
      --pdb_dir "$BACKBONE_DIR" \
      --motif_tsv "$MOTIF_TSV" \
      --trb_dir "$TRB_DIR" \
      --output_jsonl "$MPNN_DIR/fixed_positions.jsonl" \
      --strict
    "$PYTHON_BIN" "$BASE/repos/ProteinMPNN/protein_mpnn_run.py" \
      --jsonl_path "$MPNN_DIR/parsed_pdbs.jsonl" \
      --out_folder "$MPNN_DIR" \
      --num_seq_per_target "$NUM_SEQ" \
      --sampling_temp "$TEMP" \
      --seed 37 \
      --batch_size 1 \
      --fixed_positions_jsonl "$MPNN_DIR/fixed_positions.jsonl"
    ;;
  filter)
    "$PYTHON_BIN" "$BASE/scripts/filter_designs.py" \
      --input_dir "$PRED_DIR" \
      --pdb_dir "$PRED_DIR" \
      --reference_pdb "$REFERENCE_PDB" \
      --motif_tsv "$MOTIF_TSV" \
      --trb_dir "$TRB_DIR" \
      --min_plddt "$MIN_PLDDT" \
      --max_pae "$MAX_PAE" \
      --max_motif_rmsd "$MAX_MOTIF_RMSD" \
      --max_clashes "$MAX_CLASHES" \
      --output_csv "$TASK_DIR/filter_summary.csv"
    ;;
  *)
    echo "Unknown STAGE=$STAGE; use STAGE=mpnn or STAGE=filter." >&2
    exit 2
    ;;
esac
