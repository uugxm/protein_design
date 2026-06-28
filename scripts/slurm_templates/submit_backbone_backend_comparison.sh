#!/bin/bash
set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
TEMPLATE_DIR="${TEMPLATE_DIR:-$BASE/scripts/slurm_templates}"
STAMP="$(date +%Y%m%d_%H%M%S)"
COMPARE_ROOT="${COMPARE_ROOT:-$BASE/examples/epitope_scaffold/backend_comparison_${STAMP}}"

INPUT_PDB="${INPUT_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
REFERENCE_PDB="${REFERENCE_PDB:-$INPUT_PDB}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
NUM_DESIGNS="${NUM_DESIGNS:-10}"
NUM_SEQ="${NUM_SEQ:-4}"
PREDICT_MAX_RECORDS="${PREDICT_MAX_RECORDS:-2}"
PREDICTOR="${PREDICTOR:-af3}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"
BACKENDS="${BACKENDS:-rfdiffusion_v1 rfdiffusion_all_atom_legacy foundry_rfd3}"
V1_CONTIGS="${V1_CONTIGS:-[10-40/A163-181/10-40]}"
LEGACY_AA_CONTIGS="${LEGACY_AA_CONTIGS:-[\"10-40,A163-181,10-40\"]}"
LEGACY_AA_T="${LEGACY_AA_T:-100}"
FOUNDRY_RUNTIME="${FOUNDRY_RUNTIME:-micromamba}"
FOUNDRY_ENV_PREFIX="${FOUNDRY_ENV_PREFIX:-$BASE/envs/foundry-rfd3}"
FOUNDRY_RFD3_TIMESTEPS="${FOUNDRY_RFD3_TIMESTEPS:-50}"
FOUNDRY_RFD3_BATCH_SIZE="${FOUNDRY_RFD3_BATCH_SIZE:-2}"

mkdir -p "$COMPARE_ROOT/reports" "$COMPARE_ROOT/logs"

submit_backend() {
  backend="$1"
  run_dir="$COMPARE_ROOT/$backend"
  mkdir -p "$run_dir/logs" "$run_dir/reports" "$run_dir/rfdiffusion_outputs" "$run_dir/array_work"

  GEN_JOB="$(sbatch --parsable \
    --output="$run_dir/logs/backbone_gen-%j.out" \
    --error="$run_dir/logs/backbone_gen-%j.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",RUN_ROOT="$run_dir",BACKBONE_BACKEND="$backend",INPUT_PDB="$INPUT_PDB",MOTIF_TSV="$MOTIF_TSV",OUTPUT_PREFIX="$run_dir/rfdiffusion_outputs/design",NUM_DESIGNS="$NUM_DESIGNS",V1_CONTIGS="$V1_CONTIGS",LEGACY_AA_CONTIGS="$LEGACY_AA_CONTIGS",LEGACY_AA_T="$LEGACY_AA_T",FOUNDRY_RUNTIME="$FOUNDRY_RUNTIME",FOUNDRY_ENV_PREFIX="$FOUNDRY_ENV_PREFIX",FOUNDRY_RFD3_TIMESTEPS="$FOUNDRY_RFD3_TIMESTEPS",FOUNDRY_RFD3_BATCH_SIZE="$FOUNDRY_RFD3_BATCH_SIZE" \
    "$TEMPLATE_DIR/run_backbone_generation.sbatch")"

  TASK_LIST="$run_dir/backbone_list.txt"
  MPNN_JOB="$(sbatch --parsable \
    --dependency=afterok:"$GEN_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --output="$run_dir/logs/epi_mpnn-%A_%a.out" \
    --error="$run_dir/logs/epi_mpnn-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=mpnn,TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",MOTIF_TSV="$MOTIF_TSV",NUM_SEQ="$NUM_SEQ" \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  PRED_JOB="$(sbatch --parsable \
    --dependency=afterok:"$MPNN_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --output="$run_dir/logs/epi_predict-%A_%a.out" \
    --error="$run_dir/logs/epi_predict-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=predict,TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",PREDICTOR="$PREDICTOR",PREDICT_MAX_RECORDS="$PREDICT_MAX_RECORDS",PREDICT_SKIP_FIRST=1,PREDICT_SORT_BY_SCORE=1 \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  FILTER_JOB="$(sbatch --parsable \
    --dependency=afterany:"$PRED_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --output="$run_dir/logs/epi_filter-%A_%a.out" \
    --error="$run_dir/logs/epi_filter-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$MOTIF_TSV",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
    "$TEMPLATE_DIR/run_epitope_scaffold_filter.sbatch")"

  MERGE_JOB="$(sbatch --parsable \
    --dependency=afterany:"$FILTER_JOB" \
    --output="$run_dir/logs/epi_merge-%j.out" \
    --error="$run_dir/logs/epi_merge-%j.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",WORK_ROOT="$run_dir/array_work",OUT_DIR="$run_dir/reports",EXPECTED_BACKBONES="$NUM_DESIGNS",TOP_N=20 \
    "$TEMPLATE_DIR/run_epitope_scaffold_merge.sbatch")"

  cat > "$run_dir/job_ids.env" <<EOF
RUN_ROOT=$run_dir
BACKBONE_BACKEND=$backend
GEN_JOB=$GEN_JOB
MPNN_JOB=$MPNN_JOB
PRED_JOB=$PRED_JOB
FILTER_JOB=$FILTER_JOB
MERGE_JOB=$MERGE_JOB
EOF
  printf "%s:%s\n" "$backend" "$MERGE_JOB"
}

merge_jobs=()
backend_lines=()
compare_args=()
for backend in $BACKENDS; do
  line="$(submit_backend "$backend")"
  backend_lines+=("$line")
  merge_jobs+=("${line#*:}")
  compare_args+=(--backend "$backend=$COMPARE_ROOT/$backend")
done

dependency="$(IFS=:; echo "${merge_jobs[*]}")"

COMPARE_JOB="$(sbatch --parsable \
  --dependency=afterany:"$dependency" \
  --partition=AMD \
  --job-name=backend_compare \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --mem=4G \
  --time=00:15:00 \
  --output="$COMPARE_ROOT/logs/backend_compare-%j.out" \
  --error="$COMPARE_ROOT/logs/backend_compare-%j.err" \
  --wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/compare_backend_runs.py ${compare_args[*]} --output_csv $COMPARE_ROOT/reports/backend_comparison.csv --output_md $COMPARE_ROOT/reports/backend_comparison.md")"

RUN_PARAMS_PATH="$COMPARE_ROOT/run_params.json" python3 - \
  "$COMPARE_ROOT" "$INPUT_PDB" "$REFERENCE_PDB" "$MOTIF_TSV" "$BACKENDS" \
  "$NUM_DESIGNS" "$NUM_SEQ" "$PREDICT_MAX_RECORDS" "$V1_CONTIGS" \
  "$LEGACY_AA_CONTIGS" "$LEGACY_AA_T" "$FOUNDRY_RUNTIME" "$FOUNDRY_ENV_PREFIX" "$FOUNDRY_RFD3_TIMESTEPS" "$FOUNDRY_RFD3_BATCH_SIZE" \
  "$MIN_PLDDT" "$MAX_PAE" "$MAX_MOTIF_RMSD" "$MAX_CLASHES" <<'PY'
import json
import os
import sys

(
    compare_root, input_pdb, reference_pdb, motif_tsv, backends,
    num_designs, num_seq, predict_max_records, v1_contigs,
    legacy_aa_contigs, legacy_aa_T, foundry_runtime, foundry_env_prefix, foundry_rfd3_timesteps, foundry_rfd3_batch_size,
    min_plddt, max_pae, max_motif_rmsd, max_clashes,
) = sys.argv[1:]
data = {
    "compare_root": compare_root,
    "input_pdb": input_pdb,
    "reference_pdb": reference_pdb,
    "motif_tsv": motif_tsv,
    "backends": backends,
    "num_designs_per_backend": int(num_designs),
    "proteinmpnn_sequences_per_backbone": int(num_seq),
    "af3_predictions_per_backbone": int(predict_max_records),
    "v1_contigs": v1_contigs,
    "legacy_aa_contigs": legacy_aa_contigs,
    "legacy_aa_T": legacy_aa_T,
    "foundry_runtime": foundry_runtime,
    "foundry_env_prefix": foundry_env_prefix,
    "foundry_rfd3_timesteps": foundry_rfd3_timesteps,
    "foundry_rfd3_batch_size": int(foundry_rfd3_batch_size),
    "filter_thresholds": {
        "min_plddt": float(min_plddt),
        "max_pae": float(max_pae),
        "max_motif_rmsd": float(max_motif_rmsd),
        "max_clashes": int(max_clashes),
    },
}
with open(os.environ["RUN_PARAMS_PATH"], "w") as handle:
    json.dump(data, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY

cat > "$COMPARE_ROOT/job_ids.env" <<EOF
COMPARE_ROOT=$COMPARE_ROOT
BACKENDS=$BACKENDS
MERGE_JOBS=$dependency
COMPARE_JOB=$COMPARE_JOB
EOF

printf "COMPARE_ROOT=%s\n" "$COMPARE_ROOT"
printf "%s\n" "${backend_lines[@]}"
printf "COMPARE_JOB=%s\n" "$COMPARE_JOB"
