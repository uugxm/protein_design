#!/bin/bash
#SBATCH -J rf3_smoke_5vht
#SBATCH -p RTX3090
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --gres=gpu:rtx3090:1
#SBATCH --mem=32G
#SBATCH --time=02:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail
BASE=/public/home/yinyifan/protein_design
RUN_DIR=$BASE/examples/epitope_scaffold/rf3_smoke_5vht_20260628
OUT_DIR=$RUN_DIR/rf3_predictions
FLAT_DIR=$RUN_DIR/predictions_flat/rf3
CKPT=$BASE/weights/foundry/rf3_foundry_01_24_latest_remapped.ckpt
INPUT=$BASE/repos/foundry/models/rf3/tests/data/5vht_from_json.json
mkdir -p "$OUT_DIR" "$FLAT_DIR"
module purge || true
module load cuda/12.4 || true
export PATH=$BASE/envs/foundry-rfd3/bin:$PATH
export FOUNDRY_CHECKPOINT_DIRS=$BASE/weights/foundry
cd $BASE/repos/foundry
hostname
nvidia-smi -L
python - <<"PY"
import torch
print("torch.cuda.is_available=", torch.cuda.is_available())
if torch.cuda.is_available():
    print("torch.cuda.device_count=", torch.cuda.device_count())
    print("torch.cuda.device_name=", torch.cuda.get_device_name(0))
PY
rf3 fold inputs="$INPUT" out_dir="$OUT_DIR" ckpt_path="$CKPT"
python $BASE/scripts/collect_prediction_outputs.py --predictor rf3 --input_dir "$OUT_DIR" --out_dir "$FLAT_DIR" --design_id rf3_smoke_5vht
python - <<"PY"
import json, pathlib
root=pathlib.Path("/public/home/yinyifan/protein_design/examples/epitope_scaffold/rf3_smoke_5vht_20260628")
summary=list((root/"rf3_predictions").rglob("*summary_confidences.json"))
ptm=None
if summary:
    payload=json.loads(summary[0].read_text())
    ptm=payload.get("ptm") or payload.get("predicted_tm_score") or payload.get("chain_ptm")
report={"status":"completed","summary_confidences":[str(p) for p in summary],"ptm":ptm,"flat_manifest":str(root/"predictions_flat/rf3/rf3_smoke_5vht.prediction_manifest.json")}
(root/"smoke_report.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
print(json.dumps(report, sort_keys=True))
PY
