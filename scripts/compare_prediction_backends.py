#!/usr/bin/env python3
"""Merge AF3/RF3/Boltz filter summaries into a consensus table."""

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Optional


def to_float(value: Optional[str]) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        val = float(value)
    except ValueError:
        return None
    if math.isnan(val):
        return None
    return val


def read_filter(path: Path, predictor: str) -> List[Dict[str, str]]:
    rows = []
    if not path.exists():
        return rows
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            row["predictor"] = predictor
            rows.append(row)
    return rows


def load_inputs(specs: List[str]) -> List[Dict[str, str]]:
    rows = []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit("--filter_summary entries must be predictor=/path/to/filter_summary.csv")
        predictor, path = spec.split("=", 1)
        rows.extend(read_filter(Path(path), predictor))
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter_summary", action="append", default=[], help="predictor=/path/to/filter_summary.csv")
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    rows = load_inputs(args.filter_summary)
    grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in rows:
        design_id = row.get("design_id") or row.get("backbone_id") or ""
        predictor = row["predictor"]
        grouped.setdefault(design_id, {})[predictor] = row

    out_rows = []
    for design_id, by_predictor in sorted(grouped.items()):
        flat = {"design_id": design_id}
        motif_values = {}
        for predictor in ("af3", "rf3", "boltz"):
            row = by_predictor.get(predictor, {})
            plddt = to_float(row.get("plddt_mean"))
            pae = to_float(row.get("pae_mean"))
            motif = to_float(row.get("motif_rmsd"))
            motif_values[predictor] = motif
            flat["%s_pass" % predictor] = row.get("pass", "")
            flat["%s_plddt_mean" % predictor] = "" if plddt is None else "%.6g" % plddt
            flat["%s_pae_mean" % predictor] = "" if pae is None else "%.6g" % pae
            flat["%s_motif_rmsd" % predictor] = "" if motif is None else "%.6g" % motif
            flat["%s_clash_count" % predictor] = row.get("clash_count", "")
            flat["%s_model_pdb" % predictor] = row.get("model_pdb", "")
            flat["%s_confidence_file" % predictor] = row.get("confidence_file", "")
            flat["%s_parse_error" % predictor] = row.get("parse_error", "")
        af3_motif = motif_values.get("af3")
        for predictor in ("rf3", "boltz"):
            other = motif_values.get(predictor)
            flat["%s_vs_af3_motif_rmsd_delta" % predictor] = (
                "" if af3_motif is None or other is None else "%.6g" % abs(other - af3_motif)
            )
        flat["predictors_with_outputs"] = str(sum(
            1 for row in by_predictor.values()
            if row.get("model_pdb") or row.get("confidence_file")
        ))
        flat["consensus_pass"] = "PASS" if by_predictor.get("af3", {}).get("pass") == "PASS" else "CHECK"
        out_rows.append(flat)

    fieldnames = [
        "design_id",
        "af3_pass", "af3_plddt_mean", "af3_pae_mean", "af3_motif_rmsd", "af3_clash_count",
        "rf3_pass", "rf3_plddt_mean", "rf3_pae_mean", "rf3_motif_rmsd", "rf3_clash_count",
        "boltz_pass", "boltz_plddt_mean", "boltz_pae_mean", "boltz_motif_rmsd", "boltz_clash_count",
        "rf3_vs_af3_motif_rmsd_delta", "boltz_vs_af3_motif_rmsd_delta",
        "predictors_with_outputs", "consensus_pass",
        "af3_model_pdb", "rf3_model_pdb", "boltz_model_pdb",
        "af3_confidence_file", "rf3_confidence_file", "boltz_confidence_file",
        "af3_parse_error", "rf3_parse_error", "boltz_parse_error",
    ]
    out_path = Path(args.output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    print("Wrote consensus summary with %d rows to %s" % (len(out_rows), out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
