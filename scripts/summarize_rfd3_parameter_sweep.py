#!/usr/bin/env python3
"""Summarize RFD3 parameter sweep conditions."""

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import median, mean
from typing import Dict, List, Optional


FIELDS = [
    "condition_id",
    "motif_definition",
    "fixed_atom_level",
    "length_bin",
    "num_raw_outputs",
    "num_selected_for_mpnn",
    "raw_motif_rmsd_median",
    "AF3_PASS",
    "AF3_pass_rate",
    "AF3_motif_RMSD_median",
    "RF3_confirmed",
    "RF3_motif_RMSD_median",
    "mean_pLDDT",
    "mean_PAE",
    "num_fold_clusters",
    "success_per_gpu_hour",
    "failure_interpretation",
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
        val = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(val) else val


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.6g" % value
    return str(value)


def floats(rows: List[Dict[str, str]], field: str) -> List[float]:
    vals = []
    for row in rows:
        value = to_float(row.get(field))
        if value is not None:
            vals.append(value)
    return vals


def pass_rows(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    return [row for row in rows if row.get("pass") == "PASS"]


def interpretation(raw_rows, af3_rows, rf3_rows, mapping_failures: int) -> str:
    raw_median = median(floats(raw_rows, "raw_backbone_motif_rmsd")) if floats(raw_rows, "raw_backbone_motif_rmsd") else None
    af3_pass = len(pass_rows(af3_rows))
    if not raw_rows:
        return "generation_or_normalization_failed_no_raw_audit"
    if mapping_failures:
        return "motif_mapping_or_normalization_issue"
    if raw_median is not None and raw_median > 2.0:
        return "raw_motif_conditioning_or_parameterization_issue"
    if af3_rows and af3_pass / max(len(af3_rows), 1) < 0.5:
        return "raw_motif_ok_but_downstream_mpnn_or_af3_instability"
    if rf3_rows and len(pass_rows(rf3_rows)) < len(rf3_rows):
        return "af3_pass_but_rf3_confirmation_instability"
    return "no_primary_failure_detected_in_mini_sweep"


def summarize_condition(condition_dir: Path) -> Dict[str, str]:
    condition = read_json(condition_dir / "condition.json")
    reports = condition_dir / "reports"
    raw_rows = read_csv(reports / "raw_backbone_motif_audit.csv")
    af3_rows = read_csv(reports / "all_filter_summary.csv")
    rf3_rows = read_csv(reports / "rf3_filter_summary.csv")
    fold_rows = read_csv(reports / "fold_clustering" / "fold_cluster_summary.csv")
    raw_rmsd = floats(raw_rows, "raw_backbone_motif_rmsd")
    af3_rmsd = floats(af3_rows, "motif_rmsd")
    rf3_rmsd = floats(rf3_rows, "motif_rmsd")
    plddt = floats(af3_rows, "plddt_mean")
    pae = floats(af3_rows, "pae_mean")
    mapping_failures = sum(1 for row in raw_rows if row.get("motif_residue_mapping_status") != "complete")
    selected = condition_dir / "selected_backbone_list.txt"
    selected_count = len(selected.read_text().splitlines()) if selected.exists() else len(raw_rows)
    return {
        "condition_id": condition.get("condition_id", condition_dir.name),
        "motif_definition": condition.get("motif_definition", ""),
        "fixed_atom_level": condition.get("fixed_atom_level", ""),
        "length_bin": condition.get("length_bin", ""),
        "num_raw_outputs": fmt(len(raw_rows)),
        "num_selected_for_mpnn": fmt(selected_count),
        "raw_motif_rmsd_median": fmt(median(raw_rmsd)) if raw_rmsd else "",
        "AF3_PASS": fmt(len(pass_rows(af3_rows))),
        "AF3_pass_rate": fmt(len(pass_rows(af3_rows)) / len(af3_rows)) if af3_rows else "",
        "AF3_motif_RMSD_median": fmt(median(af3_rmsd)) if af3_rmsd else "",
        "RF3_confirmed": fmt(len(pass_rows(rf3_rows))),
        "RF3_motif_RMSD_median": fmt(median(rf3_rmsd)) if rf3_rmsd else "",
        "mean_pLDDT": fmt(mean(plddt)) if plddt else "",
        "mean_PAE": fmt(mean(pae)) if pae else "",
        "num_fold_clusters": fmt(len(fold_rows)),
        "success_per_gpu_hour": "",
        "failure_interpretation": interpretation(raw_rows, af3_rows, rf3_rows, mapping_failures),
    }


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sweep_root", required=True)
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    root = Path(args.sweep_root)
    condition_dirs = sorted([p for p in (root / "conditions").glob("*") if p.is_dir()])
    rows = [summarize_condition(path) for path in condition_dirs]
    write_csv(Path(args.output_csv), rows)
    print("Wrote %d RFD3 parameter sweep summary rows to %s" % (len(rows), args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
