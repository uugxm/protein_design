#!/bin/bash
set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
RUN_ROOT="${RUN_ROOT:?Set RUN_ROOT to the batch run directory.}"
JOB_ENV="$RUN_ROOT/job_ids.env"
if [ -s "$JOB_ENV" ]; then
  # shellcheck disable=SC1090
  source "$JOB_ENV"
fi
PRED_JOB="${PRED_JOB:?Set PRED_JOB or provide it in $JOB_ENV.}"

TEMPLATE_DIR="${TEMPLATE_DIR:-$BASE/scripts/slurm_templates}"
TASK_LIST="${TASK_LIST:-$RUN_ROOT/backbone_list.txt}"
WORK_ROOT="${WORK_ROOT:-$RUN_ROOT/array_work}"
REFERENCE_PDB="${REFERENCE_PDB:?Set REFERENCE_PDB to the motif reference PDB/CIF.}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
PREDICTOR="${PREDICTOR:-af3}"
PREDICT_MAX_RECORDS="${PREDICT_MAX_RECORDS:-2}"
PREDICT_SKIP_FIRST="${PREDICT_SKIP_FIRST:-1}"
PREDICT_SORT_BY_SCORE="${PREDICT_SORT_BY_SCORE:-1}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"
TOP_N="${TOP_N:-20}"
EXPECTED_BACKBONES="${EXPECTED_BACKBONES:-0}"

if ! command -v sacct >/dev/null 2>&1; then
  echo "sacct is required on the Slurm login node to find failed array tasks." >&2
  exit 2
fi

FAILED_TASKS="$(
  sacct -n -P -j "$PRED_JOB" --format=JobID,State |
    awk -F'|' -v job="$PRED_JOB" '
      $1 ~ "^" job "_" && $1 !~ /\./ && $2 !~ /^COMPLETED/ {
        split($1, parts, "_");
        if (parts[2] ~ /^[0-9]+$/) print parts[2];
      }
    ' |
    sort -n -u |
    paste -sd, -
)"

if [ -z "$FAILED_TASKS" ]; then
  echo "No failed AF3 array tasks found for PRED_JOB=$PRED_JOB"
  exit 0
fi

if [ "$EXPECTED_BACKBONES" = "0" ] && [ -s "$TASK_LIST" ]; then
  EXPECTED_BACKBONES="$(wc -l < "$TASK_LIST" | tr -d ' ')"
fi

cd "$RUN_ROOT"
mkdir -p "$RUN_ROOT/logs" "$RUN_ROOT/reports"

RETRY_PRED_JOB="$(sbatch --parsable \
  --array="$FAILED_TASKS" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=predict,TASK_LIST="$TASK_LIST",WORK_ROOT="$WORK_ROOT",PREDICTOR="$PREDICTOR",PREDICT_MAX_RECORDS="$PREDICT_MAX_RECORDS",PREDICT_SKIP_FIRST="$PREDICT_SKIP_FIRST",PREDICT_SORT_BY_SCORE="$PREDICT_SORT_BY_SCORE" \
  "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

RETRY_FILTER_JOB="$(sbatch --parsable \
  --dependency=afterany:"$RETRY_PRED_JOB" \
  --array="$FAILED_TASKS" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_LIST="$TASK_LIST",WORK_ROOT="$WORK_ROOT",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$MOTIF_TSV",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
  "$TEMPLATE_DIR/run_epitope_scaffold_filter.sbatch")"

RETRY_MERGE_JOB="$(sbatch --parsable \
  --dependency=afterany:"$RETRY_FILTER_JOB" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",WORK_ROOT="$WORK_ROOT",OUT_DIR="$RUN_ROOT/reports",EXPECTED_BACKBONES="$EXPECTED_BACKBONES",TOP_N="$TOP_N" \
  "$TEMPLATE_DIR/run_epitope_scaffold_merge.sbatch")"

cat >> "$JOB_ENV" <<EOF
RETRY_FAILED_TASKS=$FAILED_TASKS
RETRY_PRED_JOB=$RETRY_PRED_JOB
RETRY_FILTER_JOB=$RETRY_FILTER_JOB
RETRY_MERGE_JOB=$RETRY_MERGE_JOB
EOF

printf "FAILED_TASKS=%s\n" "$FAILED_TASKS"
printf "RETRY_PRED_JOB=%s\nRETRY_FILTER_JOB=%s\nRETRY_MERGE_JOB=%s\n" \
  "$RETRY_PRED_JOB" "$RETRY_FILTER_JOB" "$RETRY_MERGE_JOB"
