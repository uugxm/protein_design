#!/usr/bin/env python3
"""Rank top designs using AF3+RF3 consensus, with Boltz as a warning signal."""

import argparse
import csv
from pathlib import Path


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_rows(path):
    with Path(path).open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def mean(values):
    vals = [v for v in values if v is not None]
    if not vals:
        return None
    return sum(vals) / len(vals)


def fmt(value):
    return "" if value is None else "%.6g" % value


def boltz_warning(row):
    if not row:
        return "NO_BOLTZ_RESULT"
    if row.get("prediction_status") != "SUCCESS":
        return "BOLTZ_NO_SUCCESS"
    if row.get("pass") != "PASS":
        reasons = []
        plddt = to_float(row.get("plddt_mean"))
        motif = to_float(row.get("motif_rmsd"))
        missing = to_float(row.get("motif_atoms_missing"))
        if plddt is not None and plddt < 70:
            reasons.append("low_plddt")
        if motif is not None and motif > 2.0:
            reasons.append("high_motif_rmsd")
        if missing is not None and missing > 0:
            reasons.append("motif_atoms_missing")
        return "BOLTZ_SINGLE_SEQUENCE_DISAGREEMENT:%s" % (";".join(reasons) or "filter_fail")
    return "BOLTZ_AGREES"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--consensus_csv", required=True)
    parser.add_argument("--output_csv", required=True)
    args = parser.parse_args()

    grouped = {}
    for row in read_rows(args.consensus_csv):
        grouped.setdefault(row["design_id"], {})[row["predictor"]] = row

    out_rows = []
    for design_id, by_pred in grouped.items():
        af3 = by_pred.get("af3", {})
        rf3 = by_pred.get("rf3", {})
        boltz = by_pred.get("boltz", {})
        af3_pass = af3.get("pass") == "PASS"
        rf3_pass = rf3.get("pass") == "PASS"
        consensus_pass = af3_pass and rf3_pass
        af3_motif = to_float(af3.get("motif_rmsd"))
        rf3_motif = to_float(rf3.get("motif_rmsd"))
        af3_plddt = to_float(af3.get("plddt_mean"))
        rf3_plddt = to_float(rf3.get("plddt_mean"))
        af3_pae = to_float(af3.get("pae_mean"))
        rf3_pae = to_float(rf3.get("pae_mean"))
        motif_values = [af3_motif, rf3_motif]
        plddt_values = [af3_plddt, rf3_plddt]
        pae_values = [af3_pae, rf3_pae]
        out_rows.append({
            "design_id": design_id,
            "recommendation": "RECOMMENDED" if consensus_pass else "NOT_RECOMMENDED",
            "af3_pass": af3.get("pass", ""),
            "rf3_pass": rf3.get("pass", ""),
            "af3_motif_rmsd": fmt(af3_motif),
            "rf3_motif_rmsd": fmt(rf3_motif),
            "max_af3_rf3_motif_rmsd": fmt(max([v for v in motif_values if v is not None], default=None)),
            "mean_af3_rf3_motif_rmsd": fmt(mean(motif_values)),
            "af3_plddt": fmt(af3_plddt),
            "rf3_plddt": fmt(rf3_plddt),
            "mean_af3_rf3_plddt": fmt(mean(plddt_values)),
            "af3_pae": fmt(af3_pae),
            "rf3_pae": fmt(rf3_pae),
            "mean_af3_rf3_pae": fmt(mean(pae_values)),
            "af3_clash_count": af3.get("clash_count", ""),
            "rf3_clash_count": rf3.get("clash_count", ""),
            "boltz_status": boltz.get("prediction_status", "MISSING"),
            "boltz_pass": boltz.get("pass", ""),
            "boltz_plddt": boltz.get("plddt_mean", ""),
            "boltz_ptm": boltz.get("ptm", ""),
            "boltz_motif_rmsd": boltz.get("motif_rmsd", ""),
            "boltz_warning": boltz_warning(boltz),
            "_sort": (
                0 if consensus_pass else 1,
                max([v for v in motif_values if v is not None], default=999.0),
                mean(motif_values) if mean(motif_values) is not None else 999.0,
                -(mean(plddt_values) if mean(plddt_values) is not None else -999.0),
                mean(pae_values) if mean(pae_values) is not None else 999.0,
                design_id,
            ),
        })

    out_rows.sort(key=lambda row: row["_sort"])
    fieldnames = [
        "rank", "design_id", "recommendation", "af3_pass", "rf3_pass",
        "af3_motif_rmsd", "rf3_motif_rmsd", "max_af3_rf3_motif_rmsd",
        "mean_af3_rf3_motif_rmsd", "af3_plddt", "rf3_plddt",
        "mean_af3_rf3_plddt", "af3_pae", "rf3_pae", "mean_af3_rf3_pae",
        "af3_clash_count", "rf3_clash_count", "boltz_status", "boltz_pass",
        "boltz_plddt", "boltz_ptm", "boltz_motif_rmsd", "boltz_warning",
    ]
    out_path = Path(args.output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for rank, row in enumerate(out_rows, start=1):
            row = dict(row)
            row["rank"] = rank
            row.pop("_sort", None)
            writer.writerow(row)
    print("Wrote %d ranked designs to %s" % (len(out_rows), out_path))


if __name__ == "__main__":
    main()
