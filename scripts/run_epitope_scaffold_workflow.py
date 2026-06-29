#!/usr/bin/env python3
"""Submit or materialize the reusable epitope scaffold workflow."""

import argparse
import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Dict, List


def parse_backends(text: str) -> List[str]:
    return [item for item in text.replace(",", " ").split() if item]


def run(cmd: List[str], env: Dict[str, str], cwd: Path) -> subprocess.CompletedProcess:
    print("+ " + " ".join(shlex.quote(item) for item in cmd))
    return subprocess.run(cmd, cwd=str(cwd), env=env, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def write_env(path: Path, payload: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["%s=%s" % (key, value) for key, value in payload.items()]
    path.write_text("\n".join(lines) + "\n")


def read_env(path: Path) -> Dict[str, str]:
    out = {}
    if not path.exists():
        return out
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        out[key] = value
    return out


def submit_summary_job(base: Path, benchmark_root: Path, compare_root: Path, backends: List[str], dependency: str) -> str:
    args = ["python", str(base / "scripts" / "benchmark_backbone_backends.py")]
    for backend in backends:
        args.extend(["--backend", "%s=%s" % (backend, compare_root / backend)])
    summary_csv = benchmark_root / "reports" / "backend_comparison_summary.csv"
    compare_csv = compare_root / "reports" / "backend_comparison_summary.csv"
    args.extend(["--output_csv", str(summary_csv)])
    wrap = (
        "module purge || true; module load pytorch/2.3.1 cuda/12.4 || true; "
        + " ".join(shlex.quote(item) for item in args)
        + "; cp "
        + shlex.quote(str(summary_csv))
        + " "
        + shlex.quote(str(compare_csv))
    )
    cmd = [
        "sbatch", "--parsable",
        "--dependency=afterany:%s" % dependency,
        "--partition=AMD",
        "--job-name=backend_summary",
        "--nodes=1",
        "--ntasks=1",
        "--cpus-per-task=2",
        "--mem=4G",
        "--time=00:15:00",
        "--output=%s" % (compare_root / "logs" / "backend_summary-%j.out"),
        "--error=%s" % (compare_root / "logs" / "backend_summary-%j.err"),
        "--wrap=%s" % wrap,
    ]
    proc = subprocess.run(cmd, universal_newlines=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    return proc.stdout.strip().splitlines()[-1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["smoke", "production"], default="smoke")
    parser.add_argument("--benchmark_root", required=True)
    parser.add_argument("--input_pdb", required=True)
    parser.add_argument("--reference_pdb", default="")
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--backends", default="rfdiffusion_v1,foundry_rfd3")
    parser.add_argument("--num_backbones", type=int, default=20)
    parser.add_argument("--num_seq", type=int, default=4)
    parser.add_argument("--af3_per_backbone", type=int, default=1)
    parser.add_argument("--rf3_top_n", type=int, default=5)
    parser.add_argument("--v1_contigs", default="")
    parser.add_argument("--foundry_nterm_range", default="10-40")
    parser.add_argument("--foundry_cterm_range", default="10-40")
    parser.add_argument("--foundry_batch_size", type=int, default=2)
    parser.add_argument("--max_motif_rmsd", type=float, default=2.5)
    parser.add_argument("--min_plddt", type=float, default=70.0)
    parser.add_argument("--max_pae", type=float, default=10.0)
    parser.add_argument("--max_clashes", type=int, default=20)
    parser.add_argument("--submit", action="store_true")
    parser.add_argument("--dry_run", action="store_true")
    args = parser.parse_args()

    base = Path(os.environ.get("PROTEIN_DESIGN_HOME", Path(__file__).resolve().parents[1])).resolve()
    benchmark_root = Path(args.benchmark_root).resolve()
    compare_root = benchmark_root / ("phase1_smoke" if args.phase == "smoke" else "phase2_production")
    reports = benchmark_root / "reports"
    logs = benchmark_root / "logs"
    reports.mkdir(parents=True, exist_ok=True)
    logs.mkdir(parents=True, exist_ok=True)

    backends = parse_backends(args.backends)
    if not backends:
        raise SystemExit("No backends specified")
    if "rfdiffusion_v1" in backends and not args.v1_contigs:
        raise SystemExit("--v1_contigs is required for RFdiffusion v1 motif scaffolding")

    run_params = {
        "phase": args.phase,
        "benchmark_root": str(benchmark_root),
        "compare_root": str(compare_root),
        "input_pdb": str(Path(args.input_pdb).resolve()),
        "reference_pdb": str(Path(args.reference_pdb or args.input_pdb).resolve()),
        "motif_tsv": str(Path(args.motif_tsv).resolve()),
        "backends": backends,
        "num_backbones": args.num_backbones,
        "num_proteinmpnn_sequences_per_backbone": args.num_seq,
        "af3_predictions_per_backbone": args.af3_per_backbone,
        "rf3_top_n_per_backend": args.rf3_top_n,
        "v1_contigs": args.v1_contigs,
        "foundry_nterm_range": args.foundry_nterm_range,
        "foundry_cterm_range": args.foundry_cterm_range,
        "foundry_batch_size": args.foundry_batch_size,
        "filters": {
            "min_plddt": args.min_plddt,
            "max_pae": args.max_pae,
            "max_motif_rmsd": args.max_motif_rmsd,
            "max_clashes": args.max_clashes,
        },
        "notes": [
            "5TPN contact4/contact5 extraction is provenance for motif choice.",
            "RF3 confirmation and final packaging run after AF3 summary selects top candidates.",
            "Boltz no-MSA is a warning layer only.",
        ],
    }
    write_json(benchmark_root / "run_params.json", run_params)

    env = os.environ.copy()
    env.update({
        "PROTEIN_DESIGN_HOME": str(base),
        "COMPARE_ROOT": str(compare_root),
        "INPUT_PDB": str(Path(args.input_pdb).resolve()),
        "REFERENCE_PDB": str(Path(args.reference_pdb or args.input_pdb).resolve()),
        "MOTIF_TSV": str(Path(args.motif_tsv).resolve()),
        "BACKENDS": " ".join(backends),
        "NUM_DESIGNS": str(args.num_backbones),
        "NUM_SEQ": str(args.num_seq),
        "PREDICT_MAX_RECORDS": str(args.af3_per_backbone),
        "PREDICTOR": "af3",
        "V1_CONTIGS": args.v1_contigs,
        "FOUNDRY_RFD3_NTERM_RANGE": args.foundry_nterm_range,
        "FOUNDRY_RFD3_CTERM_RANGE": args.foundry_cterm_range,
        "FOUNDRY_RFD3_BATCH_SIZE": str(args.foundry_batch_size),
        "MIN_PLDDT": str(args.min_plddt),
        "MAX_PAE": str(args.max_pae),
        "MAX_MOTIF_RMSD": str(args.max_motif_rmsd),
        "MAX_CLASHES": str(args.max_clashes),
    })

    submit_script = base / "scripts" / "slurm_templates" / "submit_backbone_backend_comparison.sh"
    if args.dry_run or not args.submit:
        write_env(benchmark_root / "job_ids.env", {
            "STATUS": "dry_run",
            "COMPARE_ROOT": str(compare_root),
            "BACKENDS": " ".join(backends),
            "SUBMIT_SCRIPT": str(submit_script),
        })
        print(json.dumps({"dry_run": True, "compare_root": str(compare_root), "run_params": str(benchmark_root / "run_params.json")}, indent=2))
        return 0

    proc = run(["bash", str(submit_script)], env, base)
    print(proc.stdout)
    job_env = read_env(compare_root / "job_ids.env")
    compare_job = job_env.get("COMPARE_JOB", "")
    if not compare_job:
        raise SystemExit("Could not recover COMPARE_JOB from %s" % (compare_root / "job_ids.env"))
    summary_job = submit_summary_job(base, benchmark_root, compare_root, backends, compare_job)
    write_env(benchmark_root / "job_ids.env", {
        "STATUS": "submitted",
        "COMPARE_ROOT": str(compare_root),
        "BACKENDS": " ".join(backends),
        "COMPARE_JOB": compare_job,
        "BACKEND_SUMMARY_JOB": summary_job,
        "RF3_TOP_N": str(args.rf3_top_n),
    })
    print("BACKEND_SUMMARY_JOB=%s" % summary_job)
    print("COMPARE_ROOT=%s" % compare_root)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
