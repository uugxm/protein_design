#!/bin/bash
#SBATCH -J epi_merge
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 2
#SBATCH --mem=4G
#SBATCH --time=00:15:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python}"
WORK_ROOT="${WORK_ROOT:-$PWD/array_work}"
OUT_DIR="${OUT_DIR:-$PWD}"
EXPECTED_BACKBONES="${EXPECTED_BACKBONES:-0}"
TOP_N="${TOP_N:-20}"

mkdir -p logs "$OUT_DIR"
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true

"$PYTHON_BIN" "$BASE/scripts/merge_filter_summaries.py" \
  --work_root "$WORK_ROOT" \
  --output_csv "$OUT_DIR/all_filter_summary.csv" \
  --top_csv "$OUT_DIR/top_designs.csv" \
  --run_report_json "$OUT_DIR/run_report.json" \
  --expected_backbones "$EXPECTED_BACKBONES" \
  --top_n "$TOP_N"
