#!/bin/bash
set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
TEMPLATE_DIR="${TEMPLATE_DIR:-$BASE/scripts/slurm_templates}"
STAMP="$(date +%Y%m%d_%H%M%S)"
RUN_ROOT="${RUN_ROOT:-$BASE/examples/epitope_scaffold/batch_${STAMP}}"

INPUT_PDB="${INPUT_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
REFERENCE_PDB="${REFERENCE_PDB:-$INPUT_PDB}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
CONTIGS="${CONTIGS:-[10-40/A163-181/10-40]}"
NUM_DESIGNS="${NUM_DESIGNS:-20}"
NUM_SEQ="${NUM_SEQ:-4}"
TEMP="${TEMP:-0.1}"
PREDICTOR="${PREDICTOR:-af3}"
PREDICT_MAX_RECORDS="${PREDICT_MAX_RECORDS:-2}"
PREDICT_SKIP_FIRST="${PREDICT_SKIP_FIRST:-1}"
PREDICT_SORT_BY_SCORE="${PREDICT_SORT_BY_SCORE:-1}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-2.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"
TOP_N="${TOP_N:-20}"

case "$NUM_DESIGNS" in
  ''|*[!0-9]*) echo "NUM_DESIGNS must be an integer" >&2; exit 2 ;;
esac
case "$NUM_SEQ" in
  ''|*[!0-9]*) echo "NUM_SEQ must be an integer" >&2; exit 2 ;;
esac
if [ "$NUM_DESIGNS" -lt 10 ] || [ "$NUM_DESIGNS" -gt 50 ]; then
  echo "NUM_DESIGNS must be between 10 and 50 for this production template." >&2
  exit 2
fi
if [ "$NUM_SEQ" -lt 4 ] || [ "$NUM_SEQ" -gt 8 ]; then
  echo "NUM_SEQ must be between 4 and 8 for this production template." >&2
  exit 2
fi

mkdir -p "$RUN_ROOT/logs" "$RUN_ROOT/reports" "$RUN_ROOT/rfdiffusion_outputs" "$RUN_ROOT/array_work"

TASK_LIST="$RUN_ROOT/backbone_list.txt"
for idx in $(seq 0 $((NUM_DESIGNS - 1))); do
  printf "%s/rfdiffusion_outputs/design_%d.pdb\n" "$RUN_ROOT" "$idx"
done > "$TASK_LIST"

cat > "$RUN_ROOT/run_params.json" <<EOF
{
  "run_root": "$RUN_ROOT",
  "input_pdb": "$INPUT_PDB",
  "reference_pdb": "$REFERENCE_PDB",
  "motif_tsv": "$MOTIF_TSV",
  "contigs": "$CONTIGS",
  "rfdiffusion_backbones": $NUM_DESIGNS,
  "proteinmpnn_sequences_per_backbone": $NUM_SEQ,
  "proteinmpnn_sampling_temp": "$TEMP",
  "predictor": "$PREDICTOR",
  "predictions_per_backbone": $PREDICT_MAX_RECORDS,
  "prediction_selection": "ProteinMPNN FASTA records sorted by ascending score= after skipping the native/first record",
  "filter_thresholds": {
    "min_plddt": $MIN_PLDDT,
    "max_pae": $MAX_PAE,
    "max_motif_rmsd": $MAX_MOTIF_RMSD,
    "max_clashes": $MAX_CLASHES
  },
  "ranking_order": [
    "plddt_mean descending",
    "pae_mean ascending",
    "motif_rmsd ascending",
    "clash_count ascending"
  ]
}
EOF

cd "$RUN_ROOT"

RF_JOB="$(sbatch --parsable \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",INPUT_PDB="$INPUT_PDB",OUTPUT_PREFIX="$RUN_ROOT/rfdiffusion_outputs/design",CONTIGS="$CONTIGS",NUM_DESIGNS="$NUM_DESIGNS" \
  "$TEMPLATE_DIR/run_rfdiffusion_epitope.sbatch")"

MPNN_JOB="$(sbatch --parsable \
  --dependency=afterok:"$RF_JOB" \
  --array=1-"$NUM_DESIGNS" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=mpnn,TASK_LIST="$TASK_LIST",WORK_ROOT="$RUN_ROOT/array_work",MOTIF_TSV="$MOTIF_TSV",NUM_SEQ="$NUM_SEQ",TEMP="$TEMP" \
  "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

PRED_JOB="$(sbatch --parsable \
  --dependency=afterok:"$MPNN_JOB" \
  --array=1-"$NUM_DESIGNS" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=predict,TASK_LIST="$TASK_LIST",WORK_ROOT="$RUN_ROOT/array_work",PREDICTOR="$PREDICTOR",PREDICT_MAX_RECORDS="$PREDICT_MAX_RECORDS",PREDICT_SKIP_FIRST="$PREDICT_SKIP_FIRST",PREDICT_SORT_BY_SCORE="$PREDICT_SORT_BY_SCORE" \
  "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

FILTER_JOB="$(sbatch --parsable \
  --dependency=afterany:"$PRED_JOB" \
  --array=1-"$NUM_DESIGNS" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_LIST="$TASK_LIST",WORK_ROOT="$RUN_ROOT/array_work",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$MOTIF_TSV",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
  "$TEMPLATE_DIR/run_epitope_scaffold_filter.sbatch")"

MERGE_JOB="$(sbatch --parsable \
  --dependency=afterany:"$FILTER_JOB" \
  --export=ALL,PROTEIN_DESIGN_HOME="$BASE",WORK_ROOT="$RUN_ROOT/array_work",OUT_DIR="$RUN_ROOT/reports",EXPECTED_BACKBONES="$NUM_DESIGNS",TOP_N="$TOP_N" \
  "$TEMPLATE_DIR/run_epitope_scaffold_merge.sbatch")"

cat > "$RUN_ROOT/job_ids.env" <<EOF
RUN_ROOT=$RUN_ROOT
RF_JOB=$RF_JOB
MPNN_JOB=$MPNN_JOB
PRED_JOB=$PRED_JOB
FILTER_JOB=$FILTER_JOB
MERGE_JOB=$MERGE_JOB
EOF

cat > "$RUN_ROOT/af3_retry_instructions.txt" <<EOF
If any AF3 prediction array task fails after PRED_JOB=$PRED_JOB finishes, retry
only failed array indices and refresh CPU filtering/merge with:

  cd $BASE
  RUN_ROOT=$RUN_ROOT PRED_JOB=$PRED_JOB \\
    bash scripts/retry_failed_af3_predictions.sh

This creates RETRY_PRED_JOB, RETRY_FILTER_JOB and RETRY_MERGE_JOB entries in
$RUN_ROOT/job_ids.env. The final summary remains in:

  $RUN_ROOT/reports/all_filter_summary.csv
  $RUN_ROOT/reports/top_designs.csv
  $RUN_ROOT/reports/run_report.json
EOF

printf "RUN_ROOT=%s\n" "$RUN_ROOT"
printf "RF_JOB=%s\nMPNN_JOB=%s\nPRED_JOB=%s\nFILTER_JOB=%s\nMERGE_JOB=%s\n" \
  "$RF_JOB" "$MPNN_JOB" "$PRED_JOB" "$FILTER_JOB" "$MERGE_JOB"
printf "Run params: %s\n" "$RUN_ROOT/run_params.json"
printf "Retry instructions: %s\n" "$RUN_ROOT/af3_retry_instructions.txt"
