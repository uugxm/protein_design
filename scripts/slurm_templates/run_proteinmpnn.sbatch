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
PDB_DIR="${PDB_DIR:-$PWD/backbones}"
OUT_DIR="${OUT_DIR:-$PWD/mpnn_outputs}"
NUM_SEQ="${NUM_SEQ:-4}"
TEMP="${TEMP:-0.1}"

mkdir -p logs "$OUT_DIR"
hostname
nvidia-smi -L || true
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true

cd "$MPNN_REPO"
python helper_scripts/parse_multiple_chains.py \
  --input_path="$PDB_DIR" \
  --output_path="$OUT_DIR/parsed_pdbs.jsonl"

python protein_mpnn_run.py \
  --jsonl_path "$OUT_DIR/parsed_pdbs.jsonl" \
  --out_folder "$OUT_DIR" \
  --num_seq_per_target "$NUM_SEQ" \
  --sampling_temp "$TEMP" \
  --seed 37 \
  --batch_size 1
