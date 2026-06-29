#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_ROOT="$(cd "$ROOT/.." && pwd)"
BASE="${PROTEIN_DESIGN_HOME:-$(cd "$BENCHMARK_ROOT/../.." && pwd)}"
export PROTEIN_DESIGN_HOME="$BASE"

TEMPLATE_DIR="${TEMPLATE_DIR:-$BASE/scripts/slurm_templates}"
PARAM_SWEEP_ROOT="${PARAM_SWEEP_ROOT:-$BENCHMARK_ROOT/rfd3_parameter_sweep}"
INPUT_PDB="${INPUT_PDB:-$ROOT/inputs/5TPN.pdb}"
REFERENCE_PDB="${REFERENCE_PDB:-$INPUT_PDB}"
CONTACT_CORE_TSV="${CONTACT_CORE_TSV:-$ROOT/inputs/motif_residues_core_A169_178.tsv}"
MANIFEST="${MANIFEST:-$ROOT/condition_manifest.tsv}"
SUBMIT="${SUBMIT:-1}"

NUM_RAW_OUTPUTS="${NUM_RAW_OUTPUTS:-20}"
NUM_SELECTED_FOR_MPNN="${NUM_SELECTED_FOR_MPNN:-20}"
NUM_PROTEINMPNN_SEQUENCES="${NUM_PROTEINMPNN_SEQUENCES:-5}"
AF3_PER_BACKBONE="${AF3_PER_BACKBONE:-1}"
RF3_TOP_N="${RF3_TOP_N:-5}"
FOUNDRY_RFD3_BATCH_SIZE="${FOUNDRY_RFD3_BATCH_SIZE:-2}"
FOUNDRY_RFD3_TIMESTEPS="${FOUNDRY_RFD3_TIMESTEPS:-50}"
FOUNDRY_RFD3_STEP_SCALE="${FOUNDRY_RFD3_STEP_SCALE:-1.5}"
FOUNDRY_RFD3_ETA="${FOUNDRY_RFD3_ETA:-not_supported_or_not_exposed}"
FOUNDRY_RFD3_GAMMA_0="${FOUNDRY_RFD3_GAMMA_0:-0.6}"
FOUNDRY_RFD3_CFG_SCALE="${FOUNDRY_RFD3_CFG_SCALE:-1.5}"
FOUNDRY_RFD3_CENTER_OPTION="${FOUNDRY_RFD3_CENTER_OPTION:-all}"
FOUNDRY_RFD3_ALLOW_REALIGNMENT="${FOUNDRY_RFD3_ALLOW_REALIGNMENT:-False}"
FOUNDRY_RFD3_PARTIAL_T="${FOUNDRY_RFD3_PARTIAL_T:-not_set}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"

mkdir -p "$ROOT/reports" "$ROOT/logs" "$ROOT/conditions"

submit_wrap() {
  job_name="$1"
  dependency="$2"
  stdout="$3"
  stderr="$4"
  wrap="$5"
  dep_args=()
  if [ -n "$dependency" ]; then
    dep_args=(--dependency="$dependency")
  fi
  sbatch --parsable \
    "${dep_args[@]}" \
    --partition=AMD \
    --job-name="$job_name" \
    --nodes=1 \
    --ntasks=1 \
    --cpus-per-task=2 \
    --mem=4G \
    --time=00:30:00 \
    --output="$stdout" \
    --error="$stderr" \
    --wrap="$wrap"
}

manifest_value() {
  python3 - "$MANIFEST" "$1" "$2" <<'PY'
import csv
import sys
manifest, condition_id, field = sys.argv[1:]
with open(manifest, newline="") as handle:
    for row in csv.DictReader(handle, delimiter="\t"):
        if row["condition_id"] == condition_id:
            print(row.get(field, ""))
            raise SystemExit(0)
raise SystemExit(2)
PY
}

validation_value() {
  python3 - "$ROOT/reports/rfd3_contact_motif_input_validation.csv" "$1" "$2" <<'PY'
import csv
import sys
path, condition_id, field = sys.argv[1:]
with open(path, newline="") as handle:
    for row in csv.DictReader(handle):
        if row["condition_id"] == condition_id:
            print(row.get(field, ""))
            raise SystemExit(0)
raise SystemExit(2)
PY
}

submit_condition() {
  condition_id="$1"
  extra_dependency="$2"
  motif_tsv="$(validation_value "$condition_id" motif_tsv)"
  rfd3_input_json="$(validation_value "$condition_id" rfd3_input_json)"
  nterm_range="$(manifest_value "$condition_id" nterm_range)"
  cterm_range="$(manifest_value "$condition_id" cterm_range)"
  fixed_atoms="$(manifest_value "$condition_id" fixed_atoms)"
  condition_dir="$ROOT/conditions/$condition_id"
  mkdir -p "$condition_dir/logs" "$condition_dir/reports" "$condition_dir/rfdiffusion_outputs" "$condition_dir/array_work"

  dep_args=()
  if [ -n "$extra_dependency" ]; then
    dep_args=(--dependency="$extra_dependency")
  fi
  GEN_JOB="$(sbatch --parsable \
    "${dep_args[@]}" \
    --output="$condition_dir/logs/backbone_gen-%j.out" \
    --error="$condition_dir/logs/backbone_gen-%j.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",RUN_ROOT="$condition_dir",BACKBONE_BACKEND=foundry_rfd3,INPUT_PDB="$INPUT_PDB",MOTIF_TSV="$motif_tsv",OUTPUT_PREFIX="$condition_dir/rfdiffusion_outputs/design",NUM_DESIGNS="$NUM_RAW_OUTPUTS",FOUNDRY_RFD3_INPUT_JSON="$rfd3_input_json",FOUNDRY_RFD3_NTERM_RANGE="$nterm_range",FOUNDRY_RFD3_CTERM_RANGE="$cterm_range",FOUNDRY_RFD3_FIXED_ATOMS="$fixed_atoms",FOUNDRY_RFD3_TIMESTEPS="$FOUNDRY_RFD3_TIMESTEPS",FOUNDRY_RFD3_STEP_SCALE="$FOUNDRY_RFD3_STEP_SCALE",FOUNDRY_RFD3_ETA="$FOUNDRY_RFD3_ETA",FOUNDRY_RFD3_GAMMA_0="$FOUNDRY_RFD3_GAMMA_0",FOUNDRY_RFD3_CFG_SCALE="$FOUNDRY_RFD3_CFG_SCALE",FOUNDRY_RFD3_CENTER_OPTION="$FOUNDRY_RFD3_CENTER_OPTION",FOUNDRY_RFD3_ALLOW_REALIGNMENT="$FOUNDRY_RFD3_ALLOW_REALIGNMENT",FOUNDRY_RFD3_PARTIAL_T="$FOUNDRY_RFD3_PARTIAL_T",FOUNDRY_RFD3_BATCH_SIZE="$FOUNDRY_RFD3_BATCH_SIZE" \
    "$TEMPLATE_DIR/run_backbone_generation.sbatch")"

  raw_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/audit_backbone_motifs.py --backend foundry_rfd3=$condition_dir --reference_pdb $REFERENCE_PDB --motif_tsv $motif_tsv --output_csv $condition_dir/reports/raw_backbone_motif_audit.csv"
  RAW_JOB="$(submit_wrap "${condition_id}_raw" "afterok:$GEN_JOB" "$condition_dir/logs/raw_audit-%j.out" "$condition_dir/logs/raw_audit-%j.err" "$raw_wrap")"

  select_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/select_backbones_from_raw_audit.py --audit_csv $condition_dir/reports/raw_backbone_motif_audit.csv --output_list $condition_dir/selected_backbone_list.txt --output_tsv $condition_dir/reports/selected_backbones.tsv --top_n $NUM_SELECTED_FOR_MPNN"
  SELECT_JOB="$(submit_wrap "${condition_id}_select" "afterok:$RAW_JOB" "$condition_dir/logs/select-%j.out" "$condition_dir/logs/select-%j.err" "$select_wrap")"

  MPNN_JOB="$(sbatch --parsable \
    --dependency=afterok:"$SELECT_JOB" \
    --array=1-"$NUM_SELECTED_FOR_MPNN" \
    --output="$condition_dir/logs/epi_mpnn-%A_%a.out" \
    --error="$condition_dir/logs/epi_mpnn-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=mpnn,TASK_LIST="$condition_dir/selected_backbone_list.txt",WORK_ROOT="$condition_dir/array_work",MOTIF_TSV="$motif_tsv",NUM_SEQ="$NUM_PROTEINMPNN_SEQUENCES" \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  PRED_JOB="$(sbatch --parsable \
    --dependency=afterok:"$MPNN_JOB" \
    --array=1-"$NUM_SELECTED_FOR_MPNN" \
    --output="$condition_dir/logs/epi_predict-%A_%a.out" \
    --error="$condition_dir/logs/epi_predict-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=predict,TASK_LIST="$condition_dir/selected_backbone_list.txt",WORK_ROOT="$condition_dir/array_work",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$motif_tsv",PREDICTOR=af3,PREDICT_MAX_RECORDS="$AF3_PER_BACKBONE",PREDICT_SKIP_FIRST=1,PREDICT_SORT_BY_SCORE=1 \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  FILTER_JOB="$(sbatch --parsable \
    --dependency=afterany:"$PRED_JOB" \
    --array=1-"$NUM_SELECTED_FOR_MPNN" \
    --output="$condition_dir/logs/epi_filter-%A_%a.out" \
    --error="$condition_dir/logs/epi_filter-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_LIST="$condition_dir/selected_backbone_list.txt",WORK_ROOT="$condition_dir/array_work",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$motif_tsv",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
    "$TEMPLATE_DIR/run_epitope_scaffold_filter.sbatch")"

  MERGE_JOB="$(sbatch --parsable \
    --dependency=afterany:"$FILTER_JOB" \
    --output="$condition_dir/logs/epi_merge-%j.out" \
    --error="$condition_dir/logs/epi_merge-%j.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",WORK_ROOT="$condition_dir/array_work",OUT_DIR="$condition_dir/reports",EXPECTED_BACKBONES="$NUM_SELECTED_FOR_MPNN",TOP_N=20 \
    "$TEMPLATE_DIR/run_epitope_scaffold_merge.sbatch")"

  rf3_select_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/select_rf3_confirmation_tasks.py --af3_summary $condition_dir/reports/all_filter_summary.csv --run_dir $condition_dir --output_tsv $condition_dir/reports/rf3_confirmation_tasks.tsv --top_n $RF3_TOP_N"
  RF3_SELECT_JOB="$(submit_wrap "${condition_id}_rf3sel" "afterany:$MERGE_JOB" "$condition_dir/logs/rf3_select-%j.out" "$condition_dir/logs/rf3_select-%j.err" "$rf3_select_wrap")"

  RF3_JOB="$(sbatch --parsable \
    --dependency=afterok:"$RF3_SELECT_JOB" \
    --array=1-"$RF3_TOP_N" \
    --output="$condition_dir/logs/rf3_confirm-%A_%a.out" \
    --error="$condition_dir/logs/rf3_confirm-%A_%a.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_TSV="$condition_dir/reports/rf3_confirmation_tasks.tsv",WORK_ROOT="$condition_dir/rf3_confirmations",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$motif_tsv",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
    "$TEMPLATE_DIR/run_rf3_confirmation_from_manifest.sbatch")"

  rf3_merge_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/merge_filter_summaries.py --work_root $condition_dir/rf3_confirmations --output_csv $condition_dir/reports/rf3_filter_summary.csv --top_csv $condition_dir/reports/rf3_top_designs.csv --run_report_json $condition_dir/reports/rf3_run_report.json --expected_backbones $RF3_TOP_N --top_n $RF3_TOP_N"
  RF3_MERGE_JOB="$(submit_wrap "${condition_id}_rf3merge" "afterany:$RF3_JOB" "$condition_dir/logs/rf3_merge-%j.out" "$condition_dir/logs/rf3_merge-%j.err" "$rf3_merge_wrap")"

  contact_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/contact_face_qc.py --condition_id $condition_id --condition_dir $condition_dir --reference_complex $REFERENCE_PDB --contact_residue_tsv $CONTACT_CORE_TSV --antigen_chain A --antibody_chains H,L --af3_summary $condition_dir/reports/all_filter_summary.csv --rf3_summary $condition_dir/reports/rf3_filter_summary.csv --output_csv $condition_dir/reports/contact_face_qc.csv --output_md $condition_dir/reports/contact_face_qc_summary.md"
  CONTACT_QC_JOB="$(submit_wrap "${condition_id}_cfqc" "afterany:$RF3_MERGE_JOB" "$condition_dir/logs/contact_qc-%j.out" "$condition_dir/logs/contact_qc-%j.err" "$contact_wrap")"

  consensus_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/compare_prediction_backends.py --filter_summary af3=$condition_dir/reports/all_filter_summary.csv --filter_summary rf3=$condition_dir/reports/rf3_filter_summary.csv --output_csv $condition_dir/reports/consensus_summary.csv --summary_json $condition_dir/reports/consensus_summary.json --summary_md $condition_dir/reports/consensus_summary.md"
  CONSENSUS_JOB="$(submit_wrap "${condition_id}_cons" "afterany:$RF3_MERGE_JOB" "$condition_dir/logs/consensus-%j.out" "$condition_dir/logs/consensus-%j.err" "$consensus_wrap")"

  cluster_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/cluster_fold_diversity.py --summary_csv $condition_dir/reports/consensus_summary.csv --pdb_dir $condition_dir --reference_pdb $REFERENCE_PDB --motif_tsv $motif_tsv --out_dir $condition_dir/reports/fold_clustering --predictor consensus --min_plddt $MIN_PLDDT --max_pae $MAX_PAE --max_motif_rmsd $MAX_MOTIF_RMSD --max_clashes $MAX_CLASHES"
  CLUSTER_JOB="$(submit_wrap "${condition_id}_cluster" "afterany:$CONSENSUS_JOB" "$condition_dir/logs/cluster-%j.out" "$condition_dir/logs/cluster-%j.err" "$cluster_wrap")"

  {
    echo "${condition_id}_GEN_JOB=$GEN_JOB"
    echo "${condition_id}_RAW_AUDIT_JOB=$RAW_JOB"
    echo "${condition_id}_SELECT_JOB=$SELECT_JOB"
    echo "${condition_id}_MPNN_JOB=$MPNN_JOB"
    echo "${condition_id}_AF3_JOB=$PRED_JOB"
    echo "${condition_id}_FILTER_JOB=$FILTER_JOB"
    echo "${condition_id}_MERGE_JOB=$MERGE_JOB"
    echo "${condition_id}_RF3_SELECT_JOB=$RF3_SELECT_JOB"
    echo "${condition_id}_RF3_JOB=$RF3_JOB"
    echo "${condition_id}_RF3_MERGE_JOB=$RF3_MERGE_JOB"
    echo "${condition_id}_CONTACT_QC_JOB=$CONTACT_QC_JOB"
    echo "${condition_id}_CONSENSUS_JOB=$CONSENSUS_JOB"
    echo "${condition_id}_CLUSTER_JOB=$CLUSTER_JOB"
  } >> "$ROOT/reports/job_ids.env"
  FINAL_JOBS+=("$CLUSTER_JOB" "$CONTACT_QC_JOB")
  LAST_CONDITION_FINAL_JOB="$CONTACT_QC_JOB"
}

python3 "$BASE/scripts/validate_rfd3_motif_input.py" \
  --manifest "$MANIFEST" \
  --pilot_root "$ROOT" \
  --output_csv "$ROOT/reports/rfd3_contact_motif_input_validation.csv" \
  --output_md "$ROOT/reports/rfd3_contact_motif_input_validation.md"

if [ "$SUBMIT" != "1" ]; then
  echo "Dry run only. Validation complete; set SUBMIT=1 to submit Slurm jobs."
  exit 0
fi

: > "$ROOT/reports/job_ids.env"

c04_status="$(validation_value c04_contact_core_a169_178_all_20_30 input_validation_status)"
if [ "$c04_status" != "valid_ready_to_run" ]; then
  echo "c04 validation status is $c04_status; refusing GPU run." >&2
  exit 2
fi

FINAL_JOBS=()
LAST_CONDITION_FINAL_JOB=""

c03_condition_dir="$PARAM_SWEEP_ROOT/conditions/rfd3_c03_a163_181_all_20_30"
c03_contact_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/contact_face_qc.py --condition_id c03_a163_181_all_20_30 --condition_dir $c03_condition_dir --reference_complex $REFERENCE_PDB --contact_residue_tsv $CONTACT_CORE_TSV --antigen_chain A --antibody_chains H,L --af3_summary $c03_condition_dir/reports/all_filter_summary.csv --rf3_summary $c03_condition_dir/reports/rf3_filter_summary.csv --output_csv $ROOT/reports/contact_face_qc_c03.csv --output_md $ROOT/reports/contact_face_qc_c03_summary.md"
C03_CONTACT_QC_JOB="$(submit_wrap c03_contact_qc "" "$ROOT/logs/c03_contact_qc-%j.out" "$ROOT/logs/c03_contact_qc-%j.err" "$c03_contact_wrap")"
echo "c03_CONTACT_QC_JOB=$C03_CONTACT_QC_JOB" >> "$ROOT/reports/job_ids.env"
FINAL_JOBS+=("$C03_CONTACT_QC_JOB")

submit_condition c04_contact_core_a169_178_all_20_30 ""
c04_final="$LAST_CONDITION_FINAL_JOB"

c05_status="$(validation_value c05_discontinuous_contact_unindex_all input_validation_status)"
c05_gpu="$(validation_value c05_discontinuous_contact_unindex_all gpu_run_allowed)"
if [ "$c05_status" = "valid_ready_to_run" ] && [ "$c05_gpu" = "yes" ]; then
  submit_condition c05_discontinuous_contact_unindex_all "afterok:$c04_final"
else
  echo "Skipping c05 GPU run: status=$c05_status gpu_run_allowed=$c05_gpu"
  echo "c05_GPU_RUN_SKIPPED=status:$c05_status" >> "$ROOT/reports/job_ids.env"
fi

summary_dependency="$(IFS=:; echo "${FINAL_JOBS[*]}")"
summary_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/summarize_rfd3_contact_motif_pilot.py --pilot_root $ROOT --parameter_sweep_root $PARAM_SWEEP_ROOT --output_csv $ROOT/reports/rfd3_contact_motif_pilot_summary.csv --output_md $ROOT/reports/rfd3_contact_motif_pilot_report.md"
SUMMARY_JOB="$(submit_wrap rfd3_contact_summary "afterany:$summary_dependency" "$ROOT/logs/rfd3_contact_summary-%j.out" "$ROOT/logs/rfd3_contact_summary-%j.err" "$summary_wrap")"
echo "RFD3_CONTACT_MOTIF_PILOT_SUMMARY_JOB=$SUMMARY_JOB" >> "$ROOT/reports/job_ids.env"

echo "RFD3 contact motif pilot submitted."
echo "PILOT_ROOT=$ROOT"
echo "c04_STATUS=$c04_status"
echo "c05_STATUS=$c05_status"
echo "SUMMARY_JOB=$SUMMARY_JOB"
