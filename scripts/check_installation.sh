#!/usr/bin/env bash
set -uo pipefail

BASE="${PROTEIN_DESIGN_HOME:-$HOME/protein_design}"
OLD_BASE="${LEGACY_PROTEIN_DESIGN_HOME:-$HOME/protein-design}"

pass() { printf "PASS\t%s\t%s\n" "$1" "$2"; }
fail() { printf "FAIL\t%s\t%s\n" "$1" "$2"; }
warn() { printf "WARN\t%s\t%s\n" "$1" "$2"; }

check_cmd() {
  local name="$1"
  local cmd="$2"
  if command -v "$cmd" >/dev/null 2>&1; then
    pass "$name" "$(command -v "$cmd")"
  else
    fail "$name" "not on PATH"
  fi
}

printf "protein_design_home\t%s\n" "$BASE"
printf "legacy_home\t%s\n" "$OLD_BASE"
printf "host\t%s\n" "$(hostname 2>/dev/null || echo unknown)"
printf "date\t%s\n" "$(date -Iseconds 2>/dev/null || date)"

check_cmd slurm_sinfo sinfo
check_cmd slurm_sbatch sbatch
check_cmd apptainer apptainer
check_cmd singularity singularity
check_cmd git git
check_cmd curl curl
check_cmd wget wget
check_cmd python3 python3

if command -v module >/dev/null 2>&1; then
  pass modules "$(module --version 2>&1 | head -1)"
else
  fail modules "environment modules command unavailable"
fi

if [ -x "$BASE/envs/rfdiffusion-se3nv/bin/python" ]; then
  RF_PY="$BASE/envs/rfdiffusion-se3nv/bin/python"
elif [ -x "$OLD_BASE/envs/rfdiffusion-se3nv/bin/python" ]; then
  RF_PY="$OLD_BASE/envs/rfdiffusion-se3nv/bin/python"
else
  RF_PY=""
fi

if [ -n "$RF_PY" ]; then
  RF_LIB="$(dirname "$(dirname "$RF_PY")")/lib"
  if LD_LIBRARY_PATH="$RF_LIB:${LD_LIBRARY_PATH:-}" "$RF_PY" - <<'PY' >/tmp/rfdiffusion_check.$$ 2>&1
import torch
import rfdiffusion
print("torch", torch.__version__, "cuda", torch.version.cuda, "available", torch.cuda.is_available())
PY
  then
    pass rfdiffusion_import "$(cat /tmp/rfdiffusion_check.$$)"
  else
    fail rfdiffusion_import "$(tr '\n' ' ' </tmp/rfdiffusion_check.$$ | cut -c1-240)"
  fi
  rm -f /tmp/rfdiffusion_check.$$
else
  fail rfdiffusion_import "RFdiffusion env python not found"
fi

if [ -f "$BASE/repos/RFdiffusion/scripts/run_inference.py" ] || [ -f "$OLD_BASE/apps/RFdiffusion/scripts/run_inference.py" ]; then
  pass rfdiffusion_repo "found"
else
  fail rfdiffusion_repo "missing"
fi

if [ -f "$BASE/repos/ProteinMPNN/protein_mpnn_run.py" ] || [ -f "$OLD_BASE/apps/ProteinMPNN/protein_mpnn_run.py" ]; then
  pass proteinmpnn_repo "found"
  if command -v module >/dev/null 2>&1; then
    module purge >/dev/null 2>&1 || true
    module load pytorch/2.3.1 cuda/12.4 >/dev/null 2>&1 || true
  fi
  if python - <<'PY' >/tmp/mpnn_check.$$ 2>&1
import torch, numpy
print("torch", torch.__version__, "cuda_available", torch.cuda.is_available())
print("numpy", numpy.__version__)
PY
  then
    pass proteinmpnn_runtime "$(cat /tmp/mpnn_check.$$)"
  else
    fail proteinmpnn_runtime "$(tr '\n' ' ' </tmp/mpnn_check.$$ | cut -c1-240)"
  fi
  rm -f /tmp/mpnn_check.$$
else
  fail proteinmpnn_repo "missing"
fi

for tool in LigandMPNN BindCraft RFantibody rf_diffusion_all_atom ColabDesign boltz; do
  if [ -d "$BASE/repos/$tool/.git" ]; then
    pass "$tool" "$(git -C "$BASE/repos/$tool" rev-parse --short HEAD 2>/dev/null || echo cloned)"
  else
    warn "$tool" "repo not installed; see docs/failure_log.md and retry commands"
  fi
done

if [ -e "$BASE/containers/alphafold3.sif" ] || [ -e /public/apps/alphafold3/alphafold3/alphafold3.sif ]; then
  pass alphafold3_container "found"
else
  warn alphafold3_container "not found"
fi

if command -v foldseek >/dev/null 2>&1; then pass foldseek "$(foldseek version 2>&1 | head -1)"; else warn foldseek "not on PATH"; fi
if command -v mmseqs >/dev/null 2>&1; then pass mmseqs2 "$(mmseqs version 2>&1 | head -1)"; else warn mmseqs2 "not on PATH"; fi
if command -v USalign >/dev/null 2>&1; then pass usalign "$(USalign 2>&1 | head -1)"; elif command -v TMalign >/dev/null 2>&1; then pass tmalign "$(TMalign 2>&1 | head -1)"; else warn usalign_tmalign "not on PATH"; fi
if command -v mkdssp >/dev/null 2>&1; then pass mkdssp "$(mkdssp --version 2>&1 | head -1)"; else warn mkdssp "not on PATH"; fi

printf "done\tcheck_installation\n"
