#!/bin/bash
#SBATCH -J rfantibody
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=48G
#SBATCH --time=08:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail
BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
RFAB_REPO="${RFAB_REPO:-$BASE/repos/RFantibody}"
ANTIGEN_PDB="${ANTIGEN_PDB:-$BASE/examples/antibody_design/input/antigen.pdb}"
EPITOPE="${EPITOPE:-A100,A101,A102}"
OUT_DIR="${OUT_DIR:-$PWD/rfantibody_outputs}"

mkdir -p logs "$OUT_DIR"
hostname
nvidia-smi -L || true

if [ ! -d "$RFAB_REPO" ]; then
  echo "RFantibody repo is not installed at $RFAB_REPO." >&2
  echo "Retry when GitHub clone works: git clone --depth=1 https://github.com/RosettaCommons/RFantibody $RFAB_REPO" >&2
  exit 20
fi

echo "RFantibody entrypoint not configured in this deployment."
echo "Use antigen=$ANTIGEN_PDB epitope=$EPITOPE output=$OUT_DIR after installing the RFantibody-specific environment."
