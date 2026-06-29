#!/bin/bash
#SBATCH -J rfdiff_epitope
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
RF_REPO="${RF_REPO:-$BASE/repos/RFdiffusion}"
RF_PY="${RF_PY:-$BASE/envs/rfdiffusion-se3nv/bin/python}"
INPUT_PDB="${INPUT_PDB:?Set INPUT_PDB to the reference PDB/CIF containing the motif.}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-$PWD/rfdiffusion_outputs/design}"
CONTIGS="${CONTIGS:?Set CONTIGS to the RFdiffusion motif contig, e.g. [10-40/A10-25/10-40].}"
NUM_DESIGNS="${NUM_DESIGNS:-1}"

mkdir -p logs "$(dirname "$OUTPUT_PREFIX")"
hostname
nvidia-smi -L

export LD_LIBRARY_PATH="$(dirname "$(dirname "$RF_PY")")/lib:${LD_LIBRARY_PATH:-}"
cd "$RF_REPO"
"$RF_PY" scripts/run_inference.py \
  inference.input_pdb="$INPUT_PDB" \
  inference.output_prefix="$OUTPUT_PREFIX" \
  "contigmap.contigs=$CONTIGS" \
  inference.num_designs="$NUM_DESIGNS"
