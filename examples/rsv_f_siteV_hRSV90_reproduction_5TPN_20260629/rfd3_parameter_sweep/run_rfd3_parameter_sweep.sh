#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BENCHMARK_ROOT="$(cd "$ROOT/.." && pwd)"
BASE="${PROTEIN_DESIGN_HOME:-$(cd "$BENCHMARK_ROOT/../.." && pwd)}"
export PROTEIN_DESIGN_HOME="$BASE"

TEMPLATE_DIR="${TEMPLATE_DIR:-$BASE/scripts/slurm_templates}"
PHASE1_ROOT="${PHASE1_ROOT:-$BENCHMARK_ROOT/phase1_smoke}"
INPUT_PDB="${INPUT_PDB:-$BENCHMARK_ROOT/inputs/5TPN.pdb}"
REFERENCE_PDB="${REFERENCE_PDB:-$INPUT_PDB}"
MOTIF_BENCHMARK_TSV="${MOTIF_BENCHMARK_TSV:-$BENCHMARK_ROOT/inputs/motif_residues_benchmark.tsv}"
SUBMIT="${SUBMIT:-1}"

NUM_RAW_OUTPUTS="${NUM_RAW_OUTPUTS:-20}"
NUM_SELECTED_FOR_MPNN="${NUM_SELECTED_FOR_MPNN:-20}"
NUM_PROTEINMPNN_SEQUENCES="${NUM_PROTEINMPNN_SEQUENCES:-5}"
AF3_PER_BACKBONE="${AF3_PER_BACKBONE:-1}"
RF3_TOP_N="${RF3_TOP_N:-5}"
FOUNDRY_RFD3_BATCH_SIZE="${FOUNDRY_RFD3_BATCH_SIZE:-2}"
FOUNDRY_RFD3_TIMESTEPS="${FOUNDRY_RFD3_TIMESTEPS:-50}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"

DEFAULT_CONDITIONS="rfd3_c01_a163_181_bkbn_10_40 rfd3_c02_a163_181_all_10_40 rfd3_c03_a163_181_all_20_30"
CONDITION_IDS="${CONDITION_IDS:-$DEFAULT_CONDITIONS}"

mkdir -p "$ROOT/reports" "$ROOT/logs" "$ROOT/conditions"

condition_params() {
  case "$1" in
    rfd3_c01_a163_181_bkbn_10_40)
      echo "A163-181|$MOTIF_BENCHMARK_TSV|backbone_atoms_N_CA_C_O|BKBN|10-40|10-40|10-40/motif/10-40"
      ;;
    rfd3_c02_a163_181_all_10_40)
      echo "A163-181|$MOTIF_BENCHMARK_TSV|all_motif_heavy_atoms|ALL|10-40|10-40|10-40/motif/10-40"
      ;;
    rfd3_c03_a163_181_all_20_30)
      echo "A163-181|$MOTIF_BENCHMARK_TSV|all_motif_heavy_atoms|ALL|20-30|20-30|20-30/motif/20-30"
      ;;
    rfd3_c04_a169_178_core_all_10_40)
      echo "A169-178_contact_core|$ROOT/inputs/motif_residues_core_A169_178.tsv|all_motif_heavy_atoms|ALL|10-40|10-40|10-40/motif/10-40"
      ;;
    rfd3_c05_contact5_curated_all_10_40)
      echo "contact5_discontinuous|$BENCHMARK_ROOT/inputs/motif_residues_contact5.tsv|all_motif_heavy_atoms|ALL|10-40|10-40|10-40/discontinuous_motif/10-40"
      ;;
    *)
      echo "Unknown condition id: $1" >&2
      return 2
      ;;
  esac
}

write_condition_json() {
  condition_id="$1"
  condition_dir="$2"
  motif_definition="$3"
  motif_tsv="$4"
  fixed_atom_level="$5"
  fixed_atoms="$6"
  nterm_range="$7"
  cterm_range="$8"
  length_bin="$9"
  python3 - "$condition_dir/condition.json" "$condition_id" "$motif_definition" "$motif_tsv" "$fixed_atom_level" "$fixed_atoms" "$nterm_range" "$cterm_range" "$length_bin" "$NUM_RAW_OUTPUTS" "$NUM_SELECTED_FOR_MPNN" "$NUM_PROTEINMPNN_SEQUENCES" <<'PY'
import json
import sys
(
    out, condition_id, motif_definition, motif_tsv, fixed_atom_level, fixed_atoms,
    nterm_range, cterm_range, length_bin, num_raw, num_selected, num_seq,
) = sys.argv[1:]
payload = {
    "condition_id": condition_id,
    "motif_definition": motif_definition,
    "motif_tsv": motif_tsv,
    "fixed_atom_level": fixed_atom_level,
    "foundry_fixed_atoms": fixed_atoms,
    "nterm_range": nterm_range,
    "cterm_range": cterm_range,
    "length_bin": length_bin,
    "num_raw_outputs": int(num_raw),
    "num_selected_for_mpnn": int(num_selected),
    "num_proteinmpnn_sequences_per_backbone": int(num_seq),
    "phase2_production_started": False,
}
with open(out, "w") as handle:
    json.dump(payload, handle, indent=2, sort_keys=True)
    handle.write("\n")
PY
}

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

submit_phase1_audits() {
  raw_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/audit_backbone_motifs.py --backend rfdiffusion_v1=$PHASE1_ROOT/rfdiffusion_v1 --backend foundry_rfd3=$PHASE1_ROOT/foundry_rfd3 --reference_pdb $REFERENCE_PDB --motif_tsv $MOTIF_BENCHMARK_TSV --output_csv $ROOT/reports/raw_backbone_motif_audit.csv"
  RAW_AUDIT_JOB="$(submit_wrap rfd3_raw_audit "" "$ROOT/logs/rfd3_raw_audit-%j.out" "$ROOT/logs/rfd3_raw_audit-%j.err" "$raw_wrap")"
  map_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/audit_rfd3_mapping.py --run_dir $PHASE1_ROOT/foundry_rfd3 --reference_pdb $REFERENCE_PDB --motif_tsv $MOTIF_BENCHMARK_TSV --output_csv $ROOT/reports/rfd3_mapping_audit.csv --output_md $ROOT/reports/rfd3_mapping_audit.md --pass_count 3 --fail_count 3"
  MAPPING_AUDIT_JOB="$(submit_wrap rfd3_map_audit "" "$ROOT/logs/rfd3_map_audit-%j.out" "$ROOT/logs/rfd3_map_audit-%j.err" "$map_wrap")"
  {
    echo "RAW_BACKBONE_AUDIT_JOB=$RAW_AUDIT_JOB"
    echo "RFD3_MAPPING_AUDIT_JOB=$MAPPING_AUDIT_JOB"
  } >> "$ROOT/reports/job_ids.env"
}

submit_condition() {
  condition_id="$1"
  IFS="|" read -r motif_definition motif_tsv fixed_atom_level fixed_atoms nterm_range cterm_range length_bin <<< "$(condition_params "$condition_id")"
  condition_dir="$ROOT/conditions/$condition_id"
  mkdir -p "$condition_dir/logs" "$condition_dir/reports" "$condition_dir/rfdiffusion_outputs" "$condition_dir/array_work"
  write_condition_json "$condition_id" "$condition_dir" "$motif_definition" "$motif_tsv" "$fixed_atom_level" "$fixed_atoms" "$nterm_range" "$cterm_range" "$length_bin"

  GEN_JOB="$(sbatch --parsable \
    --output="$condition_dir/logs/backbone_gen-%j.out" \
    --error="$condition_dir/logs/backbone_gen-%j.err" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",RUN_ROOT="$condition_dir",BACKBONE_BACKEND=foundry_rfd3,INPUT_PDB="$INPUT_PDB",MOTIF_TSV="$motif_tsv",OUTPUT_PREFIX="$condition_dir/rfdiffusion_outputs/design",NUM_DESIGNS="$NUM_RAW_OUTPUTS",FOUNDRY_RFD3_NTERM_RANGE="$nterm_range",FOUNDRY_RFD3_CTERM_RANGE="$cterm_range",FOUNDRY_RFD3_FIXED_ATOMS="$fixed_atoms",FOUNDRY_RFD3_TIMESTEPS="$FOUNDRY_RFD3_TIMESTEPS",FOUNDRY_RFD3_BATCH_SIZE="$FOUNDRY_RFD3_BATCH_SIZE" \
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
    echo "${condition_id}_CONSENSUS_JOB=$CONSENSUS_JOB"
    echo "${condition_id}_CLUSTER_JOB=$CLUSTER_JOB"
  } >> "$ROOT/reports/job_ids.env"
  CLUSTER_JOBS+=("$CLUSTER_JOB")
}

if [ "$SUBMIT" != "1" ]; then
  echo "Dry run only. Set SUBMIT=1 to submit Slurm jobs."
  echo "Conditions: $CONDITION_IDS"
  exit 0
fi

: > "$ROOT/reports/job_ids.env"
submit_phase1_audits

CLUSTER_JOBS=()
for condition_id in $CONDITION_IDS; do
  submit_condition "$condition_id"
done

summary_dependency="$(IFS=:; echo "${CLUSTER_JOBS[*]}")"
summary_wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/summarize_rfd3_parameter_sweep.py --sweep_root $ROOT --output_csv $ROOT/reports/rfd3_parameter_sweep_summary.csv"
SUMMARY_JOB="$(submit_wrap rfd3_sweep_summary "afterany:$summary_dependency" "$ROOT/logs/rfd3_sweep_summary-%j.out" "$ROOT/logs/rfd3_sweep_summary-%j.err" "$summary_wrap")"
echo "RFD3_SWEEP_SUMMARY_JOB=$SUMMARY_JOB" >> "$ROOT/reports/job_ids.env"

echo "RFD3 parameter sweep submitted."
echo "SWEEP_ROOT=$ROOT"
echo "CONDITIONS=$CONDITION_IDS"
echo "SUMMARY_JOB=$SUMMARY_JOB"
