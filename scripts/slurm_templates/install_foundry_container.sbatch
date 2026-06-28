#!/bin/bash
#SBATCH -J foundry_install
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 4
#SBATCH --mem=16G
#SBATCH --time=03:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
IMAGE_URI="${FOUNDRY_IMAGE_URI:-docker://rosettacommons/foundry:latest}"
SIF="${FOUNDRY_SIF:-$BASE/containers/foundry_latest.sif}"
CHECKPOINT_DIR="${FOUNDRY_CHECKPOINT_DIR:-$BASE/weights/foundry}"

mkdir -p "$BASE/containers" "$CHECKPOINT_DIR" logs

hostname
apptainer --version

if [ ! -s "$SIF" ]; then
  apptainer pull --force "$SIF" "$IMAGE_URI"
fi

echo "FOUNDRY_IMAGE_URI=$IMAGE_URI"
echo "FOUNDRY_SIF=$SIF"
echo "FOUNDRY_CHECKPOINT_DIR=$CHECKPOINT_DIR"

apptainer exec --bind "$BASE:$BASE" "$SIF" python --version
apptainer exec --bind "$BASE:$BASE" "$SIF" python - <<'PY'
import importlib.metadata as md
for name in ["rc-foundry", "torch"]:
    try:
        print(f"{name}={md.version(name)}")
    except Exception as exc:
        print(f"{name}=unavailable:{exc}")
PY
apptainer exec --bind "$BASE:$BASE" "$SIF" foundry list-available
FOUNDRY_CHECKPOINT_DIRS="$CHECKPOINT_DIR" \
  apptainer exec --bind "$BASE:$BASE" "$SIF" foundry list-installed || true
