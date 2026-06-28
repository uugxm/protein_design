#!/bin/bash
#SBATCH -J bindcraft
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
BINDCRAFT_REPO="${BINDCRAFT_REPO:-$BASE/repos/BindCraft}"
TARGET_PDB="${TARGET_PDB:-$BASE/examples/binder_design/input/target.pdb}"
TARGET_CHAIN="${TARGET_CHAIN:-A}"
HOTSPOTS="${HOTSPOTS:-A45,A46,A47}"
OUT_DIR="${OUT_DIR:-$PWD/bindcraft_outputs}"

mkdir -p logs "$OUT_DIR"
hostname
nvidia-smi -L || true

if [ ! -d "$BINDCRAFT_REPO" ]; then
  echo "BindCraft repo is not installed at $BINDCRAFT_REPO." >&2
  echo "Retry when GitHub clone works: git clone --depth=1 https://github.com/martinpacesa/BindCraft $BINDCRAFT_REPO" >&2
  exit 20
fi

echo "BindCraft entrypoints vary by release. Configure its YAML/JSON under $OUT_DIR using:"
echo "target=$TARGET_PDB chain=$TARGET_CHAIN hotspots=$HOTSPOTS"
echo "Then run the release-specific BindCraft driver from $BINDCRAFT_REPO."
