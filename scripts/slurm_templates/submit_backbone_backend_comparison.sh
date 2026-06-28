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
V1_CONTIGS="${V1_CONTIGS:-[10-40/A163-181/10-40]}"
RF3_CONTIGS="${RF3_CONTIGS:-[\"10-40,A163-181,10-40\"]}"
RF3_T="${RF3_T:-100}"

mkdir -p "$COMPARE_ROOT/reports" "$COMPARE_ROOT/logs"

submit_backend() {
  backend="$1"
  run_dir="$COMPARE_ROOT/$backend"
  mkdir -p "$run_dir/logs" "$run_dir/reports" "$run_dir/rfdiffusion_outputs" "$run_dir/array_work"

  GEN_JOB="$(sbatch --parsable \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",RUN_ROOT="$run_dir",BACKBONE_BACKEND="$backend",INPUT_PDB="$INPUT_PDB",MOTIF_TSV="$MOTIF_TSV",OUTPUT_PREFIX="$run_dir/rfdiffusion_outputs/design",NUM_DESIGNS="$NUM_DESIGNS",V1_CONTIGS="$V1_CONTIGS",RF3_CONTIGS="$RF3_CONTIGS",RF3_T="$RF3_T" \
    "$TEMPLATE_DIR/run_backbone_generation.sbatch")"

  TASK_LIST="$run_dir/backbone_list.txt"
  MPNN_JOB="$(sbatch --parsable \
    --dependency=afterok:"$GEN_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=mpnn,TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",MOTIF_TSV="$MOTIF_TSV",NUM_SEQ="$NUM_SEQ" \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  PRED_JOB="$(sbatch --parsable \
    --dependency=afterok:"$MPNN_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",STAGE=predict,TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",PREDICTOR="$PREDICTOR",PREDICT_MAX_RECORDS="$PREDICT_MAX_RECORDS",PREDICT_SKIP_FIRST=1,PREDICT_SORT_BY_SCORE=1 \
    "$TEMPLATE_DIR/run_epitope_scaffold_array.sbatch")"

  FILTER_JOB="$(sbatch --parsable \
    --dependency=afterany:"$PRED_JOB" \
    --array=1-"$NUM_DESIGNS" \
    --export=ALL,PROTEIN_DESIGN_HOME="$BASE",TASK_LIST="$TASK_LIST",WORK_ROOT="$run_dir/array_work",REFERENCE_PDB="$REFERENCE_PDB",MOTIF_TSV="$MOTIF_TSV",MIN_PLDDT="$MIN_PLDDT",MAX_PAE="$MAX_PAE",MAX_MOTIF_RMSD="$MAX_MOTIF_RMSD",MAX_CLASHES="$MAX_CLASHES" \
    "$TEMPLATE_DIR/run_epitope_scaffold_filter.sbatch")"

  MERGE_JOB="$(sbatch --parsable \
    --dependency=afterany:"$FILTER_JOB" \
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

V1_MERGE_LINE="$(submit_backend rfdiffusion_v1)"
RF3_MERGE_LINE="$(submit_backend rfdiffusion_all_atom)"
V1_MERGE_JOB="${V1_MERGE_LINE#*:}"
RF3_MERGE_JOB="${RF3_MERGE_LINE#*:}"

COMPARE_JOB="$(sbatch --parsable \
  --dependency=afterany:"$V1_MERGE_JOB":"$RF3_MERGE_JOB" \
  --partition=AMD \
  --job-name=backend_compare \
  --nodes=1 \
  --ntasks=1 \
  --cpus-per-task=2 \
  --mem=4G \
  --time=00:15:00 \
  --output="$COMPARE_ROOT/logs/backend_compare-%j.out" \
  --error="$COMPARE_ROOT/logs/backend_compare-%j.err" \
  --wrap="module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; python $BASE/scripts/compare_backend_runs.py --backend rfdiffusion_v1=$COMPARE_ROOT/rfdiffusion_v1 --backend rfdiffusion_all_atom=$COMPARE_ROOT/rfdiffusion_all_atom --output_csv $COMPARE_ROOT/reports/backend_comparison.csv --output_md $COMPARE_ROOT/reports/backend_comparison.md")"

cat > "$COMPARE_ROOT/run_params.json" <<EOF
{
  "compare_root": "$COMPARE_ROOT",
  "input_pdb": "$INPUT_PDB",
  "reference_pdb": "$REFERENCE_PDB",
  "motif_tsv": "$MOTIF_TSV",
  "num_designs_per_backend": $NUM_DESIGNS,
  "proteinmpnn_sequences_per_backbone": $NUM_SEQ,
  "af3_predictions_per_backbone": $PREDICT_MAX_RECORDS,
  "v1_contigs": "$V1_CONTIGS",
  "rf3_backend_name": "rfdiffusion_all_atom",
  "rf3_contigs": "$RF3_CONTIGS",
  "rf3_T": "$RF3_T",
  "filter_thresholds": {
    "min_plddt": $MIN_PLDDT,
    "max_pae": $MAX_PAE,
    "max_motif_rmsd": $MAX_MOTIF_RMSD,
    "max_clashes": $MAX_CLASHES
  }
}
EOF

cat > "$COMPARE_ROOT/job_ids.env" <<EOF
COMPARE_ROOT=$COMPARE_ROOT
V1_MERGE_JOB=$V1_MERGE_JOB
RF3_MERGE_JOB=$RF3_MERGE_JOB
COMPARE_JOB=$COMPARE_JOB
EOF

printf "COMPARE_ROOT=%s\n" "$COMPARE_ROOT"
printf "%s\n%s\n" "$V1_MERGE_LINE" "$RF3_MERGE_LINE"
printf "COMPARE_JOB=%s\n" "$COMPARE_JOB"
