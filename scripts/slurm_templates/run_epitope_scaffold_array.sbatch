#!/bin/bash
#SBATCH -J epi_array
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=24G
#SBATCH --time=02:00:00
#SBATCH -o logs/%x-%A_%a.out
#SBATCH -e logs/%x-%A_%a.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
PYTHON_BIN="${PYTHON_BIN:-python}"
STAGE="${STAGE:-mpnn}"
TASK_LIST="${TASK_LIST:-$PWD/backbone_list.txt}"
WORK_ROOT="${WORK_ROOT:-$PWD/array_work}"
REFERENCE_PDB="${REFERENCE_PDB:-$BASE/examples/epitope_scaffold/input/5TPN.pdb}"
MOTIF_TSV="${MOTIF_TSV:-$BASE/examples/epitope_scaffold/motif_residues.tsv}"
NUM_SEQ="${NUM_SEQ:-4}"
TEMP="${TEMP:-0.1}"
MIN_PLDDT="${MIN_PLDDT:-70}"
MAX_PAE="${MAX_PAE:-10}"
MAX_MOTIF_RMSD="${MAX_MOTIF_RMSD:-1.5}"
MAX_CLASHES="${MAX_CLASHES:-20}"
PREDICTOR="${PREDICTOR:-af3}"
PREDICT_MAX_RECORDS="${PREDICT_MAX_RECORDS:-1}"
PREDICT_SKIP_FIRST="${PREDICT_SKIP_FIRST:-1}"
PREDICT_SORT_BY_SCORE="${PREDICT_SORT_BY_SCORE:-1}"
AF3_SIF="${AF3_SIF:-/public/apps/alphafold3/alphafold3/alphafold3.0.1.sif}"
AF3_MODEL_DIR="${AF3_MODEL_DIR:-/public/shared/alphafold3/models}"
AF3_DB_DIR="${AF3_DB_DIR:-/public/shared/alphafold3}"
AF3_EXTRA_ARGS="${AF3_EXTRA_ARGS:---run_data_pipeline=False}"
AF3_BIND="${AF3_BIND:-/public/shared/alphafold3:/public/shared/alphafold3}"

mkdir -p logs "$WORK_ROOT"
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
hostname
nvidia-smi -L || true

if [ ! -s "$TASK_LIST" ]; then
  echo "Missing TASK_LIST: $TASK_LIST" >&2
  exit 2
fi

TASK_ID="${SLURM_ARRAY_TASK_ID:-1}"
ITEM="$(sed -n "${TASK_ID}p" "$TASK_LIST")"
if [ -z "$ITEM" ]; then
  echo "No item at line $TASK_ID in $TASK_LIST" >&2
  exit 2
fi

DESIGN_ID="$(basename "$ITEM" .pdb)"
TASK_DIR="$WORK_ROOT/$DESIGN_ID"
BACKBONE_DIR="$TASK_DIR/backbones"
TRB_DIR="$TASK_DIR/trb"
MPNN_DIR="$TASK_DIR/mpnn_outputs"
PRED_DIR="$TASK_DIR/predictions"
PRED_INPUT_DIR="$TASK_DIR/prediction_inputs"
PRED_FLAT_DIR="$TASK_DIR/predictions_flat"
mkdir -p "$BACKBONE_DIR" "$TRB_DIR" "$MPNN_DIR" "$PRED_DIR" "$PRED_INPUT_DIR" "$PRED_FLAT_DIR"
ln -sfn "$ITEM" "$BACKBONE_DIR/$DESIGN_ID.pdb"
if [ -s "${ITEM%.pdb}.trb" ]; then
  ln -sfn "${ITEM%.pdb}.trb" "$TRB_DIR/$DESIGN_ID.trb"
fi

case "$STAGE" in
  mpnn)
    "$PYTHON_BIN" "$BASE/repos/ProteinMPNN/helper_scripts/parse_multiple_chains.py" \
      --input_path "$BACKBONE_DIR" \
      --output_path "$MPNN_DIR/parsed_pdbs.jsonl"
    "$PYTHON_BIN" "$BASE/scripts/make_fixed_positions_jsonl.py" \
      --pdb_dir "$BACKBONE_DIR" \
      --motif_tsv "$MOTIF_TSV" \
      --trb_dir "$TRB_DIR" \
      --output_jsonl "$MPNN_DIR/fixed_positions.jsonl" \
      --strict
    "$PYTHON_BIN" "$BASE/repos/ProteinMPNN/protein_mpnn_run.py" \
      --jsonl_path "$MPNN_DIR/parsed_pdbs.jsonl" \
      --out_folder "$MPNN_DIR" \
      --num_seq_per_target "$NUM_SEQ" \
      --sampling_temp "$TEMP" \
      --seed 37 \
      --batch_size 1 \
      --fixed_positions_jsonl "$MPNN_DIR/fixed_positions.jsonl"
    ;;
  predict)
    FASTA_PATH="${FASTA_PATH:-$MPNN_DIR/seqs/$DESIGN_ID.fa}"
    if [ ! -s "$FASTA_PATH" ]; then
      echo "Missing ProteinMPNN FASTA: $FASTA_PATH" >&2
      exit 2
    fi
    case "$PREDICTOR" in
      af3)
        AF3_INPUT_DIR="$PRED_INPUT_DIR/af3"
        mkdir -p "$AF3_INPUT_DIR"
        AF3_JSON_ARGS=(--fasta "$FASTA_PATH" --out_dir "$AF3_INPUT_DIR" --max_records "$PREDICT_MAX_RECORDS" --name_prefix "$DESIGN_ID" --manifest "$AF3_INPUT_DIR/manifest.tsv" --query_only)
        if [ "$PREDICT_SKIP_FIRST" = "1" ]; then
          AF3_JSON_ARGS+=(--skip_first)
        fi
        if [ "$PREDICT_SORT_BY_SCORE" = "1" ]; then
          AF3_JSON_ARGS+=(--sort_by_score)
        fi
        "$PYTHON_BIN" "$BASE/scripts/make_af3_json_inputs.py" "${AF3_JSON_ARGS[@]}"
        if [ ! -e "$AF3_SIF" ]; then
          echo "Missing AF3 container: $AF3_SIF" >&2
          exit 2
        fi
        apptainer exec --nv --bind "$AF3_BIND" "$AF3_SIF" \
          python /app/alphafold/run_alphafold.py \
            --input_dir "$AF3_INPUT_DIR" \
            --output_dir "$PRED_DIR" \
            --model_dir "$AF3_MODEL_DIR" \
            --db_dir "$AF3_DB_DIR" \
            $AF3_EXTRA_ARGS
        "$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
          --predictor af3 \
          --input_dir "$PRED_DIR" \
          --out_dir "$PRED_FLAT_DIR" \
          --design_id "$DESIGN_ID"
        ;;
      boltz)
        BOLTZ_INPUT_DIR="$PRED_INPUT_DIR/boltz"
        mkdir -p "$BOLTZ_INPUT_DIR"
        cp "$FASTA_PATH" "$BOLTZ_INPUT_DIR/$DESIGN_ID.fa"
        if ! command -v boltz >/dev/null 2>&1; then
          echo "Boltz input prepared at $BOLTZ_INPUT_DIR/$DESIGN_ID.fa, but boltz command is not installed in this environment." >&2
          exit 2
        fi
        boltz predict "$BOLTZ_INPUT_DIR/$DESIGN_ID.fa" --out_dir "$PRED_DIR"
        "$PYTHON_BIN" "$BASE/scripts/collect_prediction_outputs.py" \
          --predictor boltz \
          --input_dir "$PRED_DIR" \
          --out_dir "$PRED_FLAT_DIR" \
          --design_id "$DESIGN_ID"
        ;;
      *)
        echo "Unknown PREDICTOR=$PREDICTOR; use af3 or boltz." >&2
        exit 2
        ;;
    esac
    ;;
  filter)
    "$PYTHON_BIN" "$BASE/scripts/filter_designs.py" \
      --input_dir "$PRED_FLAT_DIR" \
      --pdb_dir "$PRED_FLAT_DIR" \
      --reference_pdb "$REFERENCE_PDB" \
      --motif_tsv "$MOTIF_TSV" \
      --trb_dir "$TRB_DIR" \
      --min_plddt "$MIN_PLDDT" \
      --max_pae "$MAX_PAE" \
      --max_motif_rmsd "$MAX_MOTIF_RMSD" \
      --max_clashes "$MAX_CLASHES" \
      --output_csv "$TASK_DIR/filter_summary.csv"
    ;;
  *)
    echo "Unknown STAGE=$STAGE; use STAGE=mpnn, STAGE=predict, or STAGE=filter." >&2
    exit 2
    ;;
esac
