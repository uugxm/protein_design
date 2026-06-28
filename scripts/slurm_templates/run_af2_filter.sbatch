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
SUMMARY_CSV="${SUMMARY_CSV:-$PWD/filter_summary.csv}"

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
  --output_csv "$SUMMARY_CSV"
