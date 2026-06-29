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

LEGACY_AA_REPO="${LEGACY_AA_REPO:-$BASE/repos/rf_diffusion_all_atom}"
LEGACY_AA_SIF="${LEGACY_AA_SIF:-$BASE/containers/rf_se3_diffusion.sif}"
LEGACY_AA_WEIGHTS="${LEGACY_AA_WEIGHTS:-$BASE/weights/RFDiffusionAA_paper_weights.pt}"
LEGACY_AA_CONTIGS="${LEGACY_AA_CONTIGS:-[\"10-40,A163-181,10-40\"]}"
LEGACY_AA_T="${LEGACY_AA_T:-100}"
LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK="${LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK:-1}"

FOUNDRY_REPO="${FOUNDRY_REPO:-$BASE/repos/foundry}"
FOUNDRY_RUNTIME="${FOUNDRY_RUNTIME:-micromamba}"
FOUNDRY_ENV_PREFIX="${FOUNDRY_ENV_PREFIX:-$BASE/envs/foundry-rfd3}"
FOUNDRY_PYTHON="${FOUNDRY_PYTHON:-$FOUNDRY_ENV_PREFIX/bin/python}"
FOUNDRY_RFD3_CMD="${FOUNDRY_RFD3_CMD:-$FOUNDRY_ENV_PREFIX/bin/rfd3}"
FOUNDRY_SIF="${FOUNDRY_SIF:-$BASE/containers/foundry_latest.sif}"
FOUNDRY_CHECKPOINT_DIR="${FOUNDRY_CHECKPOINT_DIR:-$BASE/weights/foundry}"
FOUNDRY_RFD3_INPUT_JSON="${FOUNDRY_RFD3_INPUT_JSON:-$RUN_ROOT/foundry_rfd3/input.json}"
FOUNDRY_RFD3_RAW_OUT="${FOUNDRY_RFD3_RAW_OUT:-$RUN_ROOT/foundry_rfd3/raw_outputs}"
FOUNDRY_RFD3_NTERM_RANGE="${FOUNDRY_RFD3_NTERM_RANGE:-10-40}"
FOUNDRY_RFD3_CTERM_RANGE="${FOUNDRY_RFD3_CTERM_RANGE:-10-40}"
FOUNDRY_RFD3_FIXED_ATOMS="${FOUNDRY_RFD3_FIXED_ATOMS:-BKBN}"
FOUNDRY_RFD3_TIMESTEPS="${FOUNDRY_RFD3_TIMESTEPS:-50}"
FOUNDRY_RFD3_STEP_SCALE="${FOUNDRY_RFD3_STEP_SCALE:-1.5}"
FOUNDRY_RFD3_ETA="${FOUNDRY_RFD3_ETA:-not_supported_or_not_exposed}"
FOUNDRY_RFD3_GAMMA_0="${FOUNDRY_RFD3_GAMMA_0:-0.6}"
FOUNDRY_RFD3_CFG_SCALE="${FOUNDRY_RFD3_CFG_SCALE:-1.5}"
FOUNDRY_RFD3_CENTER_OPTION="${FOUNDRY_RFD3_CENTER_OPTION:-all}"
FOUNDRY_RFD3_ALLOW_REALIGNMENT="${FOUNDRY_RFD3_ALLOW_REALIGNMENT:-False}"
FOUNDRY_RFD3_IS_NON_LOOPY="${FOUNDRY_RFD3_IS_NON_LOOPY:-True}"
FOUNDRY_RFD3_PARTIAL_T="${FOUNDRY_RFD3_PARTIAL_T:-not_set}"
FOUNDRY_RFD3_LOW_MEMORY_MODE="${FOUNDRY_RFD3_LOW_MEMORY_MODE:-True}"
FOUNDRY_RFD3_BATCH_SIZE="${FOUNDRY_RFD3_BATCH_SIZE:-$NUM_DESIGNS}"
FOUNDRY_RFD3_N_BATCHES="${FOUNDRY_RFD3_N_BATCHES:-$(((NUM_DESIGNS + FOUNDRY_RFD3_BATCH_SIZE - 1) / FOUNDRY_RFD3_BATCH_SIZE))}"

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
  rfdiffusion_all_atom_legacy)
    BACKBONE_BACKEND="rfdiffusion_all_atom_legacy"
    if [ ! -s "$LEGACY_AA_SIF" ]; then
      echo "Missing legacy RFDiffusionAA container: $LEGACY_AA_SIF" >&2
      exit 2
    fi
    if [ ! -s "$LEGACY_AA_WEIGHTS" ]; then
      echo "Missing legacy RFDiffusionAA weights: $LEGACY_AA_WEIGHTS" >&2
      exit 2
    fi
    cd "$LEGACY_AA_REPO"
    legacy_fallback_used=0
    legacy_end=$((DESIGN_STARTNUM + NUM_DESIGNS - 1))
    for design_i in $(seq "$DESIGN_STARTNUM" "$legacy_end"); do
      set +e
      apptainer run --nv "$LEGACY_AA_SIF" -u run_inference.py \
        inference.deterministic=True \
        diffuser.T="$LEGACY_AA_T" \
        inference.ckpt_path="$LEGACY_AA_WEIGHTS" \
        inference.output_prefix="$OUTPUT_PREFIX" \
        inference.input_pdb="$INPUT_PDB" \
        "contigmap.contigs=$LEGACY_AA_CONTIGS" \
        inference.num_designs=1 \
        inference.design_startnum="$design_i"
      legacy_status=$?
      set -e
      if [ "$legacy_status" -ne 0 ]; then
        unidealized_pdb="$(dirname "$OUTPUT_PREFIX")/unidealized/design_${design_i}.pdb"
        if [ "$LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK" = "1" ] && [ -s "$unidealized_pdb" ]; then
          echo "WARNING: legacy RFDiffusionAA exited $legacy_status for design_${design_i} after writing an unidealized PDB; using unidealized fallback." >&2
          cp "$unidealized_pdb" "$(dirname "$OUTPUT_PREFIX")/design_${design_i}.pdb"
          legacy_fallback_used=1
        else
          exit "$legacy_status"
        fi
      fi
    done
    if [ "$legacy_fallback_used" = "1" ]; then
      "$PYTHON_BIN" "$BASE/scripts/make_motif_mapping_from_sequence.py" \
        --reference_pdb "$INPUT_PDB" \
        --motif_tsv "$MOTIF_TSV" \
        --pdb_dir "$(dirname "$OUTPUT_PREFIX")" \
        --out_dir "$(dirname "$OUTPUT_PREFIX")" \
        --strict
    fi
    ;;
  foundry_rfd3)
    BACKBONE_BACKEND="foundry_rfd3"
    mkdir -p "$RUN_ROOT/foundry_rfd3" "$FOUNDRY_RFD3_RAW_OUT"
    foundry_input_python="$PYTHON_BIN"
    if [ "$FOUNDRY_RUNTIME" = "micromamba" ] && [ -x "$FOUNDRY_PYTHON" ]; then
      foundry_input_python="$FOUNDRY_PYTHON"
    fi
    if [ ! -s "$FOUNDRY_RFD3_INPUT_JSON" ]; then
      "$foundry_input_python" "$BASE/scripts/make_rfd3_motif_input.py" \
        --reference_pdb "$INPUT_PDB" \
        --motif_tsv "$MOTIF_TSV" \
        --output "$FOUNDRY_RFD3_INPUT_JSON" \
        --metadata_out "$RUN_ROOT/foundry_rfd3/motif_mapping_metadata.json" \
        --run_params_out "$RUN_ROOT/foundry_rfd3/rfd3_input_run_params.json" \
        --nterm_range "$FOUNDRY_RFD3_NTERM_RANGE" \
        --cterm_range "$FOUNDRY_RFD3_CTERM_RANGE" \
        --fixed_atoms "$FOUNDRY_RFD3_FIXED_ATOMS" \
        --is_non_loopy
    fi

    case "$FOUNDRY_RUNTIME" in
      micromamba)
        if [ ! -x "$FOUNDRY_RFD3_CMD" ]; then
          echo "Missing Foundry RFD3 CLI: $FOUNDRY_RFD3_CMD" >&2
          exit 2
        fi
        if [ ! -x "$FOUNDRY_PYTHON" ]; then
          echo "Missing Foundry Python: $FOUNDRY_PYTHON" >&2
          exit 2
        fi
        FOUNDRY_CHECKPOINT_DIRS="$FOUNDRY_CHECKPOINT_DIR" "$FOUNDRY_RFD3_CMD" design \
          out_dir="$FOUNDRY_RFD3_RAW_OUT" \
          inputs="$FOUNDRY_RFD3_INPUT_JSON" \
          skip_existing=False \
          prevalidate_inputs=True \
          dump_trajectories=False \
          diffusion_batch_size="$FOUNDRY_RFD3_BATCH_SIZE" \
          n_batches="$FOUNDRY_RFD3_N_BATCHES" \
          inference_sampler.num_timesteps="$FOUNDRY_RFD3_TIMESTEPS" \
          inference_sampler.step_scale="$FOUNDRY_RFD3_STEP_SCALE" \
          inference_sampler.gamma_0="$FOUNDRY_RFD3_GAMMA_0" \
          inference_sampler.cfg_scale="$FOUNDRY_RFD3_CFG_SCALE" \
          inference_sampler.center_option="$FOUNDRY_RFD3_CENTER_OPTION" \
          inference_sampler.allow_realignment="$FOUNDRY_RFD3_ALLOW_REALIGNMENT" \
          low_memory_mode="$FOUNDRY_RFD3_LOW_MEMORY_MODE"
        "$FOUNDRY_PYTHON" "$BASE/scripts/normalize_foundry_rfd3_outputs.py" \
          --input_dir "$FOUNDRY_RFD3_RAW_OUT" \
          --out_dir "$(dirname "$OUTPUT_PREFIX")" \
          --reference_pdb "$INPUT_PDB" \
          --motif_tsv "$MOTIF_TSV" \
          --max_designs "$NUM_DESIGNS" \
          --strict_mapping
        ;;
      apptainer)
        if [ ! -s "$FOUNDRY_SIF" ]; then
          echo "Missing Foundry Apptainer image: $FOUNDRY_SIF" >&2
          exit 2
        fi
        FOUNDRY_CHECKPOINT_DIRS="$FOUNDRY_CHECKPOINT_DIR" \
          apptainer exec --nv --bind "$BASE:$BASE","$RUN_ROOT:$RUN_ROOT" "$FOUNDRY_SIF" \
            rfd3 design \
              out_dir="$FOUNDRY_RFD3_RAW_OUT" \
              inputs="$FOUNDRY_RFD3_INPUT_JSON" \
              skip_existing=False \
              prevalidate_inputs=True \
              dump_trajectories=False \
              diffusion_batch_size="$FOUNDRY_RFD3_BATCH_SIZE" \
              n_batches="$FOUNDRY_RFD3_N_BATCHES" \
              inference_sampler.num_timesteps="$FOUNDRY_RFD3_TIMESTEPS" \
              inference_sampler.step_scale="$FOUNDRY_RFD3_STEP_SCALE" \
              inference_sampler.gamma_0="$FOUNDRY_RFD3_GAMMA_0" \
              inference_sampler.cfg_scale="$FOUNDRY_RFD3_CFG_SCALE" \
              inference_sampler.center_option="$FOUNDRY_RFD3_CENTER_OPTION" \
              inference_sampler.allow_realignment="$FOUNDRY_RFD3_ALLOW_REALIGNMENT" \
              low_memory_mode="$FOUNDRY_RFD3_LOW_MEMORY_MODE"
        apptainer exec --bind "$BASE:$BASE","$RUN_ROOT:$RUN_ROOT" "$FOUNDRY_SIF" \
          python "$BASE/scripts/normalize_foundry_rfd3_outputs.py" \
            --input_dir "$FOUNDRY_RFD3_RAW_OUT" \
            --out_dir "$(dirname "$OUTPUT_PREFIX")" \
            --reference_pdb "$INPUT_PDB" \
            --motif_tsv "$MOTIF_TSV" \
            --max_designs "$NUM_DESIGNS" \
            --strict_mapping
        ;;
      *)
        echo "Unknown FOUNDRY_RUNTIME=$FOUNDRY_RUNTIME; use micromamba or apptainer." >&2
        exit 2
        ;;
    esac
    ;;
  *)
    echo "Unknown BACKBONE_BACKEND=$BACKBONE_BACKEND; use rfdiffusion_v1, rfdiffusion_all_atom_legacy, or foundry_rfd3." >&2
    exit 2
    ;;
esac

find "$(dirname "$OUTPUT_PREFIX")" -maxdepth 1 -name 'design_*.pdb' | sort > "$RUN_ROOT/backbone_list.txt"

RUN_PARAMS_PATH="$RUN_ROOT/run_params.json" "$PYTHON_BIN" - \
  "$RUN_ROOT" "$BACKBONE_BACKEND" "$INPUT_PDB" "$MOTIF_TSV" "$OUTPUT_PREFIX" \
  "$NUM_DESIGNS" "$DESIGN_STARTNUM" "$V1_REPO" "$V1_CONTIGS" \
  "$LEGACY_AA_REPO" "$LEGACY_AA_SIF" "$LEGACY_AA_WEIGHTS" "$LEGACY_AA_CONTIGS" "$LEGACY_AA_T" \
  "$FOUNDRY_REPO" "$FOUNDRY_RUNTIME" "$FOUNDRY_ENV_PREFIX" "$FOUNDRY_SIF" "$FOUNDRY_CHECKPOINT_DIR" "$FOUNDRY_RFD3_INPUT_JSON" "$FOUNDRY_RFD3_RAW_OUT" "$FOUNDRY_RFD3_TIMESTEPS" "$FOUNDRY_RFD3_BATCH_SIZE" "$FOUNDRY_RFD3_N_BATCHES" "$FOUNDRY_RFD3_NTERM_RANGE" "$FOUNDRY_RFD3_CTERM_RANGE" "$FOUNDRY_RFD3_FIXED_ATOMS" "$FOUNDRY_RFD3_STEP_SCALE" "$FOUNDRY_RFD3_ETA" "$FOUNDRY_RFD3_GAMMA_0" "$FOUNDRY_RFD3_CFG_SCALE" "$FOUNDRY_RFD3_CENTER_OPTION" "$FOUNDRY_RFD3_ALLOW_REALIGNMENT" "$FOUNDRY_RFD3_IS_NON_LOOPY" "$FOUNDRY_RFD3_PARTIAL_T" \
  "$RUN_ROOT/backbone_list.txt" <<'PY'
import json
import os
import sys
from pathlib import Path

(
    run_root, backend, input_pdb, motif_tsv, output_prefix,
    num_designs, design_startnum, v1_repo, v1_contigs,
    legacy_aa_repo, legacy_aa_sif, legacy_aa_weights, legacy_aa_contigs, legacy_aa_T,
    foundry_repo, foundry_runtime, foundry_env_prefix, foundry_sif, foundry_checkpoint_dir, foundry_rfd3_input_json,
    foundry_rfd3_raw_out, foundry_rfd3_timesteps, foundry_rfd3_batch_size, foundry_rfd3_n_batches,
    foundry_rfd3_nterm_range, foundry_rfd3_cterm_range, foundry_rfd3_fixed_atoms,
    foundry_rfd3_step_scale, foundry_rfd3_eta, foundry_rfd3_gamma_0, foundry_rfd3_cfg_scale,
    foundry_rfd3_center_option, foundry_rfd3_allow_realignment, foundry_rfd3_is_non_loopy,
    foundry_rfd3_partial_t, backbone_list,
) = sys.argv[1:]
input_spec = {}
try:
    payload = json.loads(Path(foundry_rfd3_input_json).read_text())
    if isinstance(payload, dict) and payload:
        input_spec = next(iter(payload.values()))
except Exception:
    input_spec = {}
data = {
    "run_root": run_root,
    "backend": backend,
    "condition_id": input_spec.get("extra", {}).get("condition_id", ""),
    "motif_definition": input_spec.get("extra", {}).get("motif_definition", ""),
    "continuous_or_discontinuous": input_spec.get("extra", {}).get("continuous_or_discontinuous", ""),
    "fixed_atom_level": input_spec.get("extra", {}).get("fixed_atom_level", ""),
    "length_bin": input_spec.get("extra", {}).get("length_bin", ""),
    "input_pdb": input_pdb,
    "motif_tsv": motif_tsv,
    "output_prefix": output_prefix,
    "num_designs": int(num_designs),
    "design_startnum": int(design_startnum),
    "v1_repo": v1_repo,
    "v1_contigs": v1_contigs,
    "legacy_aa_repo": legacy_aa_repo,
    "legacy_aa_sif": legacy_aa_sif,
    "legacy_aa_weights": legacy_aa_weights,
    "legacy_aa_contigs": legacy_aa_contigs,
    "legacy_aa_T": legacy_aa_T,
    "foundry_repo": foundry_repo,
    "foundry_runtime": foundry_runtime,
    "foundry_env_prefix": foundry_env_prefix,
    "foundry_sif": foundry_sif,
    "foundry_checkpoint_dir": foundry_checkpoint_dir,
    "foundry_rfd3_input_json": foundry_rfd3_input_json,
    "foundry_rfd3_raw_out": foundry_rfd3_raw_out,
    "foundry_rfd3_timesteps": foundry_rfd3_timesteps,
    "foundry_rfd3_batch_size": int(foundry_rfd3_batch_size),
    "foundry_rfd3_n_batches": int(foundry_rfd3_n_batches),
    "foundry_rfd3_nterm_range": foundry_rfd3_nterm_range,
    "foundry_rfd3_cterm_range": foundry_rfd3_cterm_range,
    "foundry_rfd3_fixed_atoms": foundry_rfd3_fixed_atoms,
    "foundry_rfd3_select_fixed_atoms": input_spec.get("select_fixed_atoms", "not_supported_or_not_exposed"),
    "foundry_rfd3_contig": input_spec.get("contig", "not_supported_or_not_exposed"),
    "foundry_rfd3_unindex": input_spec.get("unindex", "not_supported_or_not_exposed"),
    "foundry_rfd3_length": input_spec.get("length", "not_supported_or_not_exposed"),
    "foundry_rfd3_select_unfixed_sequence": input_spec.get("select_unfixed_sequence", "not_supported_or_not_exposed"),
    "foundry_rfd3_step_scale": foundry_rfd3_step_scale,
    "foundry_rfd3_eta": foundry_rfd3_eta,
    "foundry_rfd3_gamma_0": foundry_rfd3_gamma_0,
    "foundry_rfd3_cfg_scale": foundry_rfd3_cfg_scale,
    "foundry_rfd3_center_option": foundry_rfd3_center_option,
    "foundry_rfd3_allow_realignment": foundry_rfd3_allow_realignment,
    "foundry_rfd3_is_non_loopy": input_spec.get("is_non_loopy", foundry_rfd3_is_non_loopy),
    "foundry_rfd3_partial_t": input_spec.get("partial_t", foundry_rfd3_partial_t),
    "foundry_rfd3_command_sampler_overrides": [
        "inference_sampler.num_timesteps=%s" % foundry_rfd3_timesteps,
        "inference_sampler.step_scale=%s" % foundry_rfd3_step_scale,
        "inference_sampler.gamma_0=%s" % foundry_rfd3_gamma_0,
        "inference_sampler.cfg_scale=%s" % foundry_rfd3_cfg_scale,
        "inference_sampler.center_option=%s" % foundry_rfd3_center_option,
        "inference_sampler.allow_realignment=%s" % foundry_rfd3_allow_realignment,
    ],
    "backbone_list": backbone_list,
}
with open(os.environ["RUN_PARAMS_PATH"], "w") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

cat > "$RUN_ROOT/backend_logs/backend.env" <<EOF
BACKBONE_BACKEND=$BACKBONE_BACKEND
INPUT_PDB=$INPUT_PDB
MOTIF_TSV=$MOTIF_TSV
OUTPUT_PREFIX=$OUTPUT_PREFIX
NUM_DESIGNS=$NUM_DESIGNS
V1_CONTIGS=$V1_CONTIGS
LEGACY_AA_CONTIGS=$LEGACY_AA_CONTIGS
LEGACY_AA_T=$LEGACY_AA_T
LEGACY_AA_SIF=$LEGACY_AA_SIF
LEGACY_AA_WEIGHTS=$LEGACY_AA_WEIGHTS
LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK=$LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK
FOUNDRY_RUNTIME=$FOUNDRY_RUNTIME
FOUNDRY_ENV_PREFIX=$FOUNDRY_ENV_PREFIX
FOUNDRY_SIF=$FOUNDRY_SIF
FOUNDRY_CHECKPOINT_DIR=$FOUNDRY_CHECKPOINT_DIR
FOUNDRY_RFD3_INPUT_JSON=$FOUNDRY_RFD3_INPUT_JSON
FOUNDRY_RFD3_TIMESTEPS=$FOUNDRY_RFD3_TIMESTEPS
FOUNDRY_RFD3_STEP_SCALE=$FOUNDRY_RFD3_STEP_SCALE
FOUNDRY_RFD3_ETA=$FOUNDRY_RFD3_ETA
FOUNDRY_RFD3_GAMMA_0=$FOUNDRY_RFD3_GAMMA_0
FOUNDRY_RFD3_CFG_SCALE=$FOUNDRY_RFD3_CFG_SCALE
FOUNDRY_RFD3_CENTER_OPTION=$FOUNDRY_RFD3_CENTER_OPTION
FOUNDRY_RFD3_ALLOW_REALIGNMENT=$FOUNDRY_RFD3_ALLOW_REALIGNMENT
FOUNDRY_RFD3_IS_NON_LOOPY=$FOUNDRY_RFD3_IS_NON_LOOPY
FOUNDRY_RFD3_PARTIAL_T=$FOUNDRY_RFD3_PARTIAL_T
FOUNDRY_RFD3_BATCH_SIZE=$FOUNDRY_RFD3_BATCH_SIZE
FOUNDRY_RFD3_N_BATCHES=$FOUNDRY_RFD3_N_BATCHES
EOF

"$PYTHON_BIN" - <<PY
from pathlib import Path
paths = sorted(Path("$(dirname "$OUTPUT_PREFIX")").glob("design_*.pdb"))
expected = int("$NUM_DESIGNS")
if len(paths) < expected:
    raise SystemExit(f"expected {expected} PDBs, found {len(paths)}")
print(f"backbone_generation_outputs={len(paths)}")
PY
