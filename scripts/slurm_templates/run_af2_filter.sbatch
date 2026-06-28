#!/bin/bash
#SBATCH -J af_filter
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=48G
#SBATCH --time=04:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail
BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
INPUT_FASTA="${INPUT_FASTA:-$PWD/input.fasta}"
PRED_DIR="${PRED_DIR:-$PWD/predictions}"
PDB_DIR="${PDB_DIR:-$PRED_DIR}"
REFERENCE_PDB="${REFERENCE_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
TRB_DIR="${TRB_DIR:-$PWD/rfdiffusion_outputs}"
SUMMARY_CSV="${SUMMARY_CSV:-$PWD/filter_summary.csv}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-1.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"

mkdir -p logs "$PRED_DIR"
hostname
nvidia-smi -L || true

if command -v colabfold_batch >/dev/null 2>&1; then
  colabfold_batch "$INPUT_FASTA" "$PRED_DIR"
elif [ -e "$BASE/containers/alphafold3.sif" ]; then
  echo "AF3 container found at $BASE/containers/alphafold3.sif"
  echo "Prepare AF3 JSON inputs, then run run_alphafold.py with --json_path/--input_dir."
else
  echo "No AF2/ColabFold command found. Prediction skipped; filtering existing JSON files only." >&2
fi

python "$BASE/scripts/filter_designs.py" \
  --input_dir "$PRED_DIR" \
  --pdb_dir "$PDB_DIR" \
  --reference_pdb "$REFERENCE_PDB" \
  --motif_tsv "$MOTIF_TSV" \
  --trb_dir "$TRB_DIR" \
  --min_plddt "$MIN_PLDDT" \
  --max_pae "$MAX_PAE" \
  --max_motif_rmsd "$MAX_MOTIF_RMSD" \
  --max_clashes "$MAX_CLASHES" \
  --output_csv "$SUMMARY_CSV"
