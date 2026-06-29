#!/usr/bin/env python3
"""Summarize RFD3 contact-core/discontinuous motif pilot results."""

import argparse
import csv
import json
import math
from pathlib import Path
from statistics import mean, median
from typing import Dict, List, Optional, Sequence


FIELDS = [
    "condition_id",
    "motif_definition",
    "continuous_or_discontinuous",
    "input_validation_status",
    "n_backbones",
    "raw_motif_rmsd_median",
    "AF3_PASS",
    "AF3_pass_rate",
    "AF3_motif_RMSD_median",
    "RF3_confirmed",
    "RF3_motif_RMSD_median",
    "AF3_contact_face_RMSD_median",
    "RF3_contact_face_RMSD_median",
    "contact_face_pass_count",
    "contact_face_caution_count",
    "contact_face_hold_count",
    "mean_pLDDT",
    "mean_PAE",
    "fold_clusters",
    "motif_local_clusters",
    "sequence_clusters",
    "interpretation",
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
        out = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(out) else out


def floats(rows: Sequence[Dict[str, str]], field: str) -> List[float]:
    vals = []
    for row in rows:
        value = to_float(row.get(field))
        if value is not None:
            vals.append(value)
    return vals


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        return "%.6g" % value
    return str(value)


def pass_count(rows: Sequence[Dict[str, str]]) -> int:
    return sum(1 for row in rows if row.get("pass") == "PASS")


def validation_map(path: Path) -> Dict[str, Dict[str, str]]:
    return {row["condition_id"]: row for row in read_csv(path)}


def contact_counts(rows: Sequence[Dict[str, str]]) -> Dict[str, int]:
    counts = {"contact_face_pass": 0, "contact_face_caution": 0, "contact_face_hold": 0}
    for row in rows:
        decision = row.get("decision", "")
        if decision in counts:
            counts[decision] += 1
    return counts


def cluster_count(path: Path) -> str:
    rows = read_csv(path)
    return str(len(rows)) if rows else ""


def summarize_condition(condition_id: str, condition_dir: Path, validation: Dict[str, Dict[str, str]], contact_qc: Path) -> Dict[str, str]:
    condition = read_json(condition_dir / "condition.json")
    reports = condition_dir / "reports"
    raw_rows = read_csv(reports / "raw_backbone_motif_audit.csv")
    af3_rows = read_csv(reports / "all_filter_summary.csv")
    rf3_rows = read_csv(reports / "rf3_filter_summary.csv")
    qc_rows = read_csv(contact_qc)
    af3_qc = [row for row in qc_rows if row.get("predictor") == "af3"]
    rf3_qc = [row for row in qc_rows if row.get("predictor") == "rf3"]
    counts = contact_counts(qc_rows)
    val = validation.get(condition_id, {})
    af3_pass = pass_count(af3_rows)
    raw_rmsd = floats(raw_rows, "raw_backbone_motif_rmsd")
    af3_rmsd = floats(af3_rows, "motif_rmsd")
    rf3_rmsd = floats(rf3_rows, "motif_rmsd")
    plddt = floats(af3_rows, "plddt_mean")
    pae = floats(af3_rows, "pae_mean")
    af3_face = floats(af3_qc, "contact_face_RMSD")
    rf3_face = floats(rf3_qc, "contact_face_RMSD")
    validation_status = val.get("input_validation_status") or ("not_run" if not raw_rows else "legacy_or_reference")
    if validation_status.startswith("hold"):
        interpretation = "validation_hold_no_gpu_run"
    elif not raw_rows:
        interpretation = "not_run_or_no_raw_audit"
    elif af3_rows and af3_pass / len(af3_rows) >= 0.5 and counts["contact_face_pass"] > 0:
        interpretation = "contact_motif_pilot_has_viable_candidates"
    elif af3_rows:
        interpretation = "scaffold_or_contact_face_qc_limited"
    else:
        interpretation = "generation_completed_but_downstream_missing"
    return {
        "condition_id": condition_id,
        "motif_definition": str(condition.get("motif_definition") or val.get("motif_definition", "")),
        "continuous_or_discontinuous": str(condition.get("continuous_or_discontinuous") or val.get("continuous_or_discontinuous", "")),
        "input_validation_status": validation_status,
        "n_backbones": fmt(len(raw_rows)),
        "raw_motif_rmsd_median": fmt(median(raw_rmsd)) if raw_rmsd else "",
        "AF3_PASS": fmt(af3_pass),
        "AF3_pass_rate": fmt(af3_pass / len(af3_rows)) if af3_rows else "",
        "AF3_motif_RMSD_median": fmt(median(af3_rmsd)) if af3_rmsd else "",
        "RF3_confirmed": fmt(pass_count(rf3_rows)),
        "RF3_motif_RMSD_median": fmt(median(rf3_rmsd)) if rf3_rmsd else "",
        "AF3_contact_face_RMSD_median": fmt(median(af3_face)) if af3_face else "",
        "RF3_contact_face_RMSD_median": fmt(median(rf3_face)) if rf3_face else "",
        "contact_face_pass_count": fmt(counts["contact_face_pass"]),
        "contact_face_caution_count": fmt(counts["contact_face_caution"]),
        "contact_face_hold_count": fmt(counts["contact_face_hold"]),
        "mean_pLDDT": fmt(mean(plddt)) if plddt else "",
        "mean_PAE": fmt(mean(pae)) if pae else "",
        "fold_clusters": cluster_count(reports / "fold_clustering" / "fold_cluster_summary.csv"),
        "motif_local_clusters": cluster_count(reports / "fold_clustering" / "motif_local_cluster_summary.csv"),
        "sequence_clusters": cluster_count(reports / "fold_clustering" / "sequence_cluster_summary.csv"),
        "interpretation": interpretation,
    }


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    by_id = {row["condition_id"]: row for row in rows}
    c04 = by_id.get("c04_contact_core_a169_178_all_20_30", {})
    c05 = by_id.get("c05_discontinuous_contact_unindex_all", {})
    c03 = by_id.get("c03_a163_181_all_20_30", {})
    lines = [
        "# RFD3 Contact-Motif Pilot Report",
        "",
        "## Status",
        "",
        "- Phase 2 production benchmark: not started.",
        "- RFdiffusion v1 baseline: not expanded.",
        "- c04 contact-core pilot status: `%s`." % c04.get("interpretation", ""),
        "- c05 discontinuous/unindex status: `%s`." % c05.get("input_validation_status", ""),
        "",
        "## Summary Table",
        "",
        "| condition | validation | AF3 pass rate | RF3 confirmed | AF3 contact-face RMSD median | RF3 contact-face RMSD median | contact-face pass/caution/hold | interpretation |",
        "| --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {condition_id} | {input_validation_status} | {AF3_pass_rate} | {RF3_confirmed} | {AF3_contact_face_RMSD_median} | {RF3_contact_face_RMSD_median} | {contact_face_pass_count}/{contact_face_caution_count}/{contact_face_hold_count} | {interpretation} |".format(**row)
        )
    lines.extend([
        "",
        "## Answers",
        "",
        "1. c04 A169-178 contact core cleanly scaffolded by RFD3: `%s`." % c04.get("interpretation", "not_available"),
        "2. c05 discontinuous contact set cleanly represented by current wrapper: `%s`." % c05.get("input_validation_status", "not_available"),
        "3. RFD3 advantage versus A163-181 continuous: compare c04 against c03; c03 remains `%s`, c04 is `%s`." % (c03.get("interpretation", "not_available"), c04.get("interpretation", "not_available")),
        "4. Contact-face QC can change ranking because it evaluates antibody-facing atom exposure, local occlusion, and contact-face RMSD separately from whole-motif RMSD.",
        "5. Candidates for expression pre-QC should only be considered from rows with `contact_face_pass` plus AF3/RF3 confirmation; see `contact_face_qc.csv` before ordering.",
        "6. RFdiffusion v1 remains the primary backend for continuous A163-181 motif reproduction.",
        "7. RFD3 small production remains blocked unless c04/c05 shows clear contact-face benefit and reviewed candidate quality.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--pilot_root", required=True)
    parser.add_argument("--parameter_sweep_root", required=True)
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--output_md", required=True)
    args = parser.parse_args()

    pilot_root = Path(args.pilot_root)
    sweep_root = Path(args.parameter_sweep_root)
    validation = validation_map(pilot_root / "reports" / "rfd3_contact_motif_input_validation.csv")
    rows = []
    rows.append(summarize_condition(
        "c03_a163_181_all_20_30",
        sweep_root / "conditions" / "rfd3_c03_a163_181_all_20_30",
        validation,
        pilot_root / "reports" / "contact_face_qc_c03.csv",
    ))
    for condition_id in ["c04_contact_core_a169_178_all_20_30", "c05_discontinuous_contact_unindex_all"]:
        rows.append(summarize_condition(
            condition_id,
            pilot_root / "conditions" / condition_id,
            validation,
            pilot_root / "conditions" / condition_id / "reports" / "contact_face_qc.csv",
        ))
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    print("Wrote %d contact motif pilot summary rows to %s" % (len(rows), args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
