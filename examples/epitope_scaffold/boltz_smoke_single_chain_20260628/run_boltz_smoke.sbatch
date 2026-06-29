#!/bin/bash
#SBATCH -J boltz_smoke
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
RUN_DIR=$BASE/examples/epitope_scaffold/boltz_smoke_single_chain_20260628
OUT_DIR=$RUN_DIR/predictions_boltz
FLAT_DIR=$RUN_DIR/predictions_flat/boltz
CACHE=$BASE/weights/boltz
mkdir -p "$OUT_DIR" "$FLAT_DIR" "$CACHE"
module purge || true
module load cuda/12.4 || true
export PATH=$BASE/envs/boltz/bin:$PATH
export BOLTZ_CACHE=$CACHE
hostname
nvidia-smi -L
python - <<"PY"
import torch
print("torch.cuda.is_available=", torch.cuda.is_available())
if torch.cuda.is_available():
    print("torch.cuda.device_count=", torch.cuda.device_count())
    print("torch.cuda.device_name=", torch.cuda.get_device_name(0))
PY
boltz predict "$RUN_DIR/input.boltz.yaml" --out_dir "$OUT_DIR" --cache "$CACHE" --sampling_steps 5 --recycling_steps 1 --diffusion_samples 1 --output_format mmcif --override --no_kernels
python $BASE/scripts/collect_prediction_outputs.py --predictor boltz --input_dir "$OUT_DIR" --out_dir "$FLAT_DIR" --design_id boltz_smoke_single_chain
python - <<"PY"
import json, pathlib, os
root=pathlib.Path("/public/home/yinyifan/protein_design/examples/epitope_scaffold/boltz_smoke_single_chain_20260628")
weights=pathlib.Path("/public/home/yinyifan/protein_design/weights/boltz")
files=[p for p in (root/"predictions_boltz").rglob("*") if p.is_file()]
report={"status":"completed","output_files":[str(p) for p in files[:50]],"flat_manifest":str(root/"predictions_flat/boltz/boltz_smoke_single_chain.prediction_manifest.json"),"boltz_cache":str(weights)}
(root/"smoke_report.json").write_text(json.dumps(report, indent=2, sort_keys=True)+"\n")
print(json.dumps(report, sort_keys=True))
PY
