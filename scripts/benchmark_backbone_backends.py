#!/usr/bin/env python3
"""Summarize RFdiffusion v1 versus Foundry RFD3 benchmark runs."""

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional


FIELDS = [
    "backend",
    "num_requested_backbones",
    "num_backbones_generated",
    "backbone_generation_success_rate",
    "backbone_walltime",
    "gpu_minutes",
    "num_mpnn_sequences",
    "num_af3_predictions",
    "num_af3_pass",
    "af3_pass_rate",
    "num_rf3_confirmed",
    "rf3_confirmation_rate",
    "mean_AF3_motif_RMSD",
    "median_AF3_motif_RMSD",
    "mean_RF3_motif_RMSD",
    "median_RF3_motif_RMSD",
    "mean_pLDDT",
    "mean_PAE",
    "clash_fail_rate",
    "motif_atoms_missing_fail_rate",
    "num_global_fold_clusters",
    "num_motif_local_clusters",
    "num_sequence_clusters",
    "top_candidate_design_ids",
    "success_per_gpu_hour",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> Dict[str, object]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(value) else value


def fmt(value) -> str:
    if value is None or value == "":
        return ""
    if isinstance(value, float):
        return "%.6g" % value
    return str(value)


def rate(numer: int, denom: int) -> str:
    return fmt(float(numer) / float(denom)) if denom else ""


def fasta_record_count(path: Path) -> int:
    count = 0
    for raw in path.read_text(errors="ignore").splitlines():
        if raw.startswith(">"):
            count += 1
    return count


def values(rows: List[Dict[str, str]], field: str) -> List[float]:
    out = []
    for row in rows:
        val = to_float(row.get(field))
        if val is not None:
            out.append(val)
    return out


def bool_fail_rows(rows: List[Dict[str, str]], field: str, fail_when_positive: bool = True) -> int:
    n = 0
    for row in rows:
        val = to_float(row.get(field))
        if val is None:
            continue
        if fail_when_positive and val > 0:
            n += 1
    return n


def design_sort_key(row: Dict[str, str]):
    passed = 0 if row.get("pass") == "PASS" or row.get("AF3 pass") == "PASS" else 1
    plddt = to_float(row.get("plddt_mean") or row.get("AF3 pLDDT"))
    pae = to_float(row.get("pae_mean") or row.get("AF3 PAE"))
    rmsd = to_float(row.get("motif_rmsd") or row.get("AF3 motif RMSD"))
    clash = to_float(row.get("clash_count"))
    return (
        passed,
        -(plddt if plddt is not None else -1e9),
        pae if pae is not None else 1e9,
        rmsd if rmsd is not None else 1e9,
        clash if clash is not None else 1e9,
        row.get("design_id", ""),
    )


def dedupe_by_backbone(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    grouped: Dict[str, List[Dict[str, str]]] = {}
    for row in rows:
        key = row.get("backbone_id") or row.get("design_id", "").split("_t_")[0]
        if not key:
            key = row.get("design_id", "")
        grouped.setdefault(key, []).append(row)
    return [sorted(group, key=design_sort_key)[0] for _key, group in sorted(grouped.items())]


def load_backend_sidecars(items: List[str]) -> Dict[str, Path]:
    out = {}
    for item in items or []:
        if "=" not in item:
            raise SystemExit("Expected name=path, got %s" % item)
        name, path = item.split("=", 1)
        out[name] = Path(path)
    return out


def summarize_backend(
    backend: str,
    run_dir: Path,
    rf3_summary: Optional[Path] = None,
    cluster_dir: Optional[Path] = None,
    sacct_row: Optional[Dict[str, str]] = None,
) -> Dict[str, str]:
    run_params = read_json(run_dir / "run_params.json")
    report = read_json(run_dir / "reports" / "run_report.json")
    filter_rows = dedupe_by_backbone(read_csv(run_dir / "reports" / "all_filter_summary.csv"))
    top_rows = read_csv(run_dir / "reports" / "top_designs.csv")
    rf3_rows = read_csv(rf3_summary) if rf3_summary else []

    requested = int(run_params.get("num_designs") or report.get("expected_backbones") or 0)
    generated = len(list((run_dir / "rfdiffusion_outputs").glob("design_*.pdb")))
    mpnn_sequences = sum(fasta_record_count(path) for path in (run_dir / "array_work").glob("*/mpnn_outputs/seqs/*.fa"))
    af3_predictions = len(filter_rows)
    af3_pass_rows = [row for row in filter_rows if row.get("pass") == "PASS"]

    if not rf3_rows:
        rf3_rows = read_csv(run_dir / "reports" / "rf3_filter_summary.csv")
    rf3_rows = dedupe_by_backbone(rf3_rows)
    rf3_pass_rows = [row for row in rf3_rows if row.get("pass") == "PASS" or row.get("RF3 pass") == "PASS"]
    rf3_total = len(rf3_rows)

    af3_rmsd = values(filter_rows, "motif_rmsd")
    rf3_rmsd = values(rf3_rows, "motif_rmsd") or values(rf3_rows, "RF3 motif RMSD")
    plddt = values(filter_rows, "plddt_mean")
    pae = values(filter_rows, "pae_mean")

    cluster_dir = cluster_dir or run_dir / "reports" / "fold_clustering"
    global_clusters = read_csv(cluster_dir / "fold_cluster_summary.csv")
    motif_clusters = read_csv(cluster_dir / "motif_local_cluster_summary.csv")
    seq_clusters = read_csv(cluster_dir / "sequence_cluster_summary.csv")
    diverse = read_csv(cluster_dir / "diverse_shortlist.csv")

    top_ids = [row.get("design_id") or row.get("backbone_id") for row in (diverse or top_rows)]
    top_ids = [item for item in top_ids if item]
    gpu_minutes = ""
    walltime = ""
    if sacct_row:
        gpu_minutes = sacct_row.get("gpu_minutes", "")
        walltime = sacct_row.get("backbone_walltime", "") or sacct_row.get("elapsed", "")
    gpu_hours = to_float(gpu_minutes)
    success_per_gpu_hour = ""
    if gpu_hours is not None and gpu_hours > 0:
        success_per_gpu_hour = fmt(len(af3_pass_rows) / (gpu_hours / 60.0))

    return {
        "backend": backend,
        "num_requested_backbones": fmt(requested),
        "num_backbones_generated": fmt(generated),
        "backbone_generation_success_rate": rate(generated, requested),
        "backbone_walltime": walltime,
        "gpu_minutes": gpu_minutes,
        "num_mpnn_sequences": fmt(mpnn_sequences),
        "num_af3_predictions": fmt(af3_predictions),
        "num_af3_pass": fmt(len(af3_pass_rows)),
        "af3_pass_rate": rate(len(af3_pass_rows), len(filter_rows)),
        "num_rf3_confirmed": fmt(len(rf3_pass_rows)),
        "rf3_confirmation_rate": rate(len(rf3_pass_rows), rf3_total),
        "mean_AF3_motif_RMSD": fmt(mean(af3_rmsd)) if af3_rmsd else "",
        "median_AF3_motif_RMSD": fmt(median(af3_rmsd)) if af3_rmsd else "",
        "mean_RF3_motif_RMSD": fmt(mean(rf3_rmsd)) if rf3_rmsd else "",
        "median_RF3_motif_RMSD": fmt(median(rf3_rmsd)) if rf3_rmsd else "",
        "mean_pLDDT": fmt(mean(plddt)) if plddt else "",
        "mean_PAE": fmt(mean(pae)) if pae else "",
        "clash_fail_rate": rate(bool_fail_rows(filter_rows, "clash_count"), len(filter_rows)),
        "motif_atoms_missing_fail_rate": rate(bool_fail_rows(filter_rows, "motif_atoms_missing"), len(filter_rows)),
        "num_global_fold_clusters": fmt(len(global_clusters)),
        "num_motif_local_clusters": fmt(len(motif_clusters)),
        "num_sequence_clusters": fmt(len(seq_clusters)),
        "top_candidate_design_ids": ";".join(top_ids[:10]),
        "success_per_gpu_hour": success_per_gpu_hour,
    }


def read_sacct(path: Optional[str]) -> Dict[str, Dict[str, str]]:
    if not path:
        return {}
    rows = read_csv(Path(path))
    return {row.get("backend", ""): row for row in rows}


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="append", required=True, help="backend_name=run_dir")
    parser.add_argument("--rf3_summary", action="append", default=[], help="backend_name=rf3_filter_summary.csv")
    parser.add_argument("--cluster_dir", action="append", default=[], help="backend_name=fold_clustering_dir")
    parser.add_argument("--sacct_tsv", default="")
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    rf3 = load_backend_sidecars(args.rf3_summary)
    clusters = load_backend_sidecars(args.cluster_dir)
    sacct = read_sacct(args.sacct_tsv)
    rows = []
    for item in args.backend:
        if "=" not in item:
            raise SystemExit("Expected --backend name=path")
        name, run_dir = item.split("=", 1)
        rows.append(summarize_backend(
            name,
            Path(run_dir),
            rf3_summary=rf3.get(name),
            cluster_dir=clusters.get(name),
            sacct_row=sacct.get(name),
        ))
    write_csv(Path(args.output_csv), rows)
    print("Wrote %s" % args.output_csv)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
