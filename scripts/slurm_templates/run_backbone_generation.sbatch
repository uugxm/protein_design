#!/bin/bash
#SBATCH -J backbone_gen
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
PYTHON_BIN="${PYTHON_BIN:-python}"
BACKBONE_BACKEND="${BACKBONE_BACKEND:-rfdiffusion_v1}"
RUN_ROOT="${RUN_ROOT:-$PWD}"
INPUT_PDB="${INPUT_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
OUTPUT_PREFIX="${OUTPUT_PREFIX:-$RUN_ROOT/rfdiffusion_outputs/design}"
NUM_DESIGNS="${NUM_DESIGNS:-1}"
DESIGN_STARTNUM="${DESIGN_STARTNUM:-0}"

V1_REPO="${V1_REPO:-$BASE/repos/RFdiffusion}"
V1_PY="${V1_PY:-$BASE/envs/rfdiffusion-se3nv/bin/python}"
V1_CONTIGS="${V1_CONTIGS:-[10-40/A163-181/10-40]}"

RF3_REPO="${RF3_REPO:-$BASE/repos/rf_diffusion_all_atom}"
RF3_SIF="${RF3_SIF:-$BASE/containers/rf_se3_diffusion.sif}"
RF3_WEIGHTS="${RF3_WEIGHTS:-$BASE/weights/RFDiffusionAA_paper_weights.pt}"
RF3_CONTIGS="${RF3_CONTIGS:-[\"10-40,A163-181,10-40\"]}"
RF3_T="${RF3_T:-100}"
RF3_ALLOW_UNIDEALIZED_FALLBACK="${RF3_ALLOW_UNIDEALIZED_FALLBACK:-1}"

mkdir -p "$RUN_ROOT/logs" "$RUN_ROOT/backend_logs" "$(dirname "$OUTPUT_PREFIX")"
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
hostname
nvidia-smi -L || true

case "$BACKBONE_BACKEND" in
  rfdiffusion_v1)
    export LD_LIBRARY_PATH="$(dirname "$(dirname "$V1_PY")")/lib:${LD_LIBRARY_PATH:-}"
    cd "$V1_REPO"
    "$V1_PY" scripts/run_inference.py \
      inference.input_pdb="$INPUT_PDB" \
      inference.output_prefix="$OUTPUT_PREFIX" \
      "contigmap.contigs=$V1_CONTIGS" \
      inference.num_designs="$NUM_DESIGNS" \
      inference.design_startnum="$DESIGN_STARTNUM"
    ;;
  rf3|rfdiffusion_all_atom)
    BACKBONE_BACKEND="rfdiffusion_all_atom"
    if [ ! -s "$RF3_SIF" ]; then
      echo "Missing RFdiffusion all-atom container: $RF3_SIF" >&2
      exit 2
    fi
    if [ ! -s "$RF3_WEIGHTS" ]; then
      echo "Missing RFdiffusion all-atom weights: $RF3_WEIGHTS" >&2
      exit 2
    fi
    cd "$RF3_REPO"
    rf3_fallback_used=0
    rf3_end=$((DESIGN_STARTNUM + NUM_DESIGNS - 1))
    for design_i in $(seq "$DESIGN_STARTNUM" "$rf3_end"); do
      set +e
      apptainer run --nv "$RF3_SIF" -u run_inference.py \
        inference.deterministic=True \
        diffuser.T="$RF3_T" \
        inference.ckpt_path="$RF3_WEIGHTS" \
        inference.output_prefix="$OUTPUT_PREFIX" \
        inference.input_pdb="$INPUT_PDB" \
        "contigmap.contigs=$RF3_CONTIGS" \
        inference.num_designs=1 \
        inference.design_startnum="$design_i"
      rf3_status=$?
      set -e
      if [ "$rf3_status" -ne 0 ]; then
        unidealized_pdb="$(dirname "$OUTPUT_PREFIX")/unidealized/design_${design_i}.pdb"
        if [ "$RF3_ALLOW_UNIDEALIZED_FALLBACK" = "1" ] && [ -s "$unidealized_pdb" ]; then
          echo "WARNING: RFDiffusionAA exited $rf3_status for design_${design_i} after writing an unidealized PDB; using unidealized fallback." >&2
          cp "$unidealized_pdb" "$(dirname "$OUTPUT_PREFIX")/design_${design_i}.pdb"
          rf3_fallback_used=1
        else
          exit "$rf3_status"
        fi
      fi
    done
    if [ "$rf3_fallback_used" = "1" ]; then
      "$PYTHON_BIN" "$BASE/scripts/make_motif_mapping_from_sequence.py" \
        --reference_pdb "$INPUT_PDB" \
        --motif_tsv "$MOTIF_TSV" \
        --pdb_dir "$(dirname "$OUTPUT_PREFIX")" \
        --out_dir "$(dirname "$OUTPUT_PREFIX")" \
        --strict
    fi
    ;;
  *)
    echo "Unknown BACKBONE_BACKEND=$BACKBONE_BACKEND; use rfdiffusion_v1 or rf3." >&2
    exit 2
    ;;
esac

find "$(dirname "$OUTPUT_PREFIX")" -maxdepth 1 -name 'design_*.pdb' | sort > "$RUN_ROOT/backbone_list.txt"

cat > "$RUN_ROOT/run_params.json" <<EOF
{
  "run_root": "$RUN_ROOT",
  "backend": "$BACKBONE_BACKEND",
  "input_pdb": "$INPUT_PDB",
  "motif_tsv": "$MOTIF_TSV",
  "output_prefix": "$OUTPUT_PREFIX",
  "num_designs": $NUM_DESIGNS,
  "design_startnum": $DESIGN_STARTNUM,
  "v1_repo": "$V1_REPO",
  "v1_contigs": "$V1_CONTIGS",
  "rf3_repo": "$RF3_REPO",
  "rf3_sif": "$RF3_SIF",
  "rf3_weights": "$RF3_WEIGHTS",
  "rf3_contigs": "$RF3_CONTIGS",
  "rf3_T": "$RF3_T",
  "backbone_list": "$RUN_ROOT/backbone_list.txt"
}
EOF

cat > "$RUN_ROOT/backend_logs/backend.env" <<EOF
BACKBONE_BACKEND=$BACKBONE_BACKEND
INPUT_PDB=$INPUT_PDB
MOTIF_TSV=$MOTIF_TSV
OUTPUT_PREFIX=$OUTPUT_PREFIX
NUM_DESIGNS=$NUM_DESIGNS
V1_CONTIGS=$V1_CONTIGS
RF3_CONTIGS=$RF3_CONTIGS
RF3_T=$RF3_T
RF3_SIF=$RF3_SIF
RF3_WEIGHTS=$RF3_WEIGHTS
RF3_ALLOW_UNIDEALIZED_FALLBACK=$RF3_ALLOW_UNIDEALIZED_FALLBACK
EOF

"$PYTHON_BIN" - <<PY
from pathlib import Path
paths = sorted(Path("$(dirname "$OUTPUT_PREFIX")").glob("design_*.pdb"))
expected = int("$NUM_DESIGNS")
if len(paths) < expected:
    raise SystemExit(f"expected {expected} PDBs, found {len(paths)}")
print(f"backbone_generation_outputs={len(paths)}")
PY
