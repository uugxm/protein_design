#!/bin/bash
#SBATCH -J foundry_mamba
#SBATCH -p AMD
#SBATCH -N 1
#SBATCH -n 1
#SBATCH -c 8
#SBATCH --mem=32G
#SBATCH --time=06:00:00
#SBATCH -o logs/%x-%j.out
#SBATCH -e logs/%x-%j.err

set -euo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
MICROMAMBA_HOME="${MICROMAMBA_HOME:-$BASE/envs/micromamba}"
MAMBA_ROOT_PREFIX="${MAMBA_ROOT_PREFIX:-$BASE/envs/micromamba-root}"
ENV_PREFIX="${FOUNDRY_ENV_PREFIX:-$BASE/envs/foundry-rfd3}"
CHECKPOINT_DIR="${FOUNDRY_CHECKPOINT_DIR:-$BASE/weights/foundry}"
MICROMAMBA_URL="${MICROMAMBA_URL:-https://micro.mamba.pm/api/micromamba/linux-64/latest}"

mkdir -p "$MICROMAMBA_HOME" "$MAMBA_ROOT_PREFIX" "$CHECKPOINT_DIR" logs
hostname

if [ ! -x "$MICROMAMBA_HOME/bin/micromamba" ]; then
  curl -L "$MICROMAMBA_URL" -o "$MICROMAMBA_HOME/micromamba.tar.bz2"
  tar -xjf "$MICROMAMBA_HOME/micromamba.tar.bz2" -C "$MICROMAMBA_HOME" bin/micromamba
fi

export MAMBA_ROOT_PREFIX
"$MICROMAMBA_HOME/bin/micromamba" create -y -p "$ENV_PREFIX" -c conda-forge python=3.12 pip

"$ENV_PREFIX/bin/python" -m pip install --upgrade pip
"$ENV_PREFIX/bin/pip" install "rc-foundry[rfd3]"

"$ENV_PREFIX/bin/python" --version
"$ENV_PREFIX/bin/python" - <<'PY'
import importlib.metadata as md
for name in ["rc-foundry", "torch"]:
    try:
        print(f"{name}={md.version(name)}")
    except Exception as exc:
        print(f"{name}=unavailable:{exc}")
PY

"$ENV_PREFIX/bin/foundry" list-available
FOUNDRY_CHECKPOINT_DIRS="$CHECKPOINT_DIR" "$ENV_PREFIX/bin/foundry" list-installed || true

if [ "${FOUNDRY_INSTALL_RFD3:-1}" = "1" ]; then
  "$ENV_PREFIX/bin/foundry" install rfd3 --checkpoint-dir "$CHECKPOINT_DIR"
  FOUNDRY_CHECKPOINT_DIRS="$CHECKPOINT_DIR" "$ENV_PREFIX/bin/foundry" list-installed
fi

cat > "$BASE/envs/foundry_rfd3_runtime.env" <<EOF
FOUNDRY_RUNTIME=micromamba
FOUNDRY_ENV_PREFIX=$ENV_PREFIX
FOUNDRY_CHECKPOINT_DIR=$CHECKPOINT_DIR
MAMBA_ROOT_PREFIX=$MAMBA_ROOT_PREFIX
MICROMAMBA=$MICROMAMBA_HOME/bin/micromamba
EOF
