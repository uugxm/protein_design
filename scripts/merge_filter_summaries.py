#!/usr/bin/env python3
"""Merge per-design filter summaries and write sorted top-design tables."""

import argparse
import csv
import json
from pathlib import Path


def to_float(value, default):
    if value in (None, ""):
        return default
    try:
        return float(value)
    except ValueError:
        return default


def read_rows(paths):
    rows = []
    for path in paths:
        with path.open("r", newline="") as handle:
            reader = csv.DictReader(handle)
            for row in reader:
                row["source_summary"] = str(path)
                task_dir = path.parent
                row["task_dir"] = str(task_dir)
                row["backbone_id"] = task_dir.name
                rows.append(row)
    return rows


def sort_key(row):
    # Higher pLDDT is better; lower PAE, motif RMSD and clash count are better.
    return (
        -to_float(row.get("plddt_mean"), -1.0),
        to_float(row.get("pae_mean"), 999999.0),
        to_float(row.get("motif_rmsd"), 999999.0),
        to_float(row.get("clash_count"), 999999.0),
        row.get("design_id", ""),
    )


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--work_root", required=True, help="Array work root containing */filter_summary.csv files.")
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--top_csv", required=True)
    parser.add_argument("--run_report_json", required=True)
    parser.add_argument("--top_n", type=int, default=20)
    parser.add_argument("--expected_backbones", type=int, default=0)
    args = parser.parse_args()

    work_root = Path(args.work_root)
    summary_paths = sorted(work_root.glob("*/filter_summary.csv"))
    rows = read_rows(summary_paths)
    rows.sort(key=sort_key)

    base_fields = []
    for row in rows:
        for key in row:
            if key not in base_fields:
                base_fields.append(key)
    preferred = [
        "backbone_id", "design_id", "pass", "plddt_mean", "pae_mean",
        "motif_rmsd", "clash_count", "ptm", "iptm", "ranking_score",
        "prediction_has_clash", "motif_atoms_compared", "motif_atoms_missing",
        "model_pdb", "confidence_file", "source_summary", "task_dir", "parse_error",
    ]
    fieldnames = preferred + [key for key in base_fields if key not in preferred]

    write_csv(Path(args.output_csv), rows, fieldnames)
    write_csv(Path(args.top_csv), rows[:args.top_n], fieldnames)

    expected = args.expected_backbones or len(summary_paths)
    passed = [r for r in rows if r.get("pass") == "PASS"]
    failures = [r for r in rows if r.get("pass") == "FAIL" or r.get("parse_error")]
    report = {
        "work_root": str(work_root),
        "summary_files": len(summary_paths),
        "expected_backbones": expected,
        "rows": len(rows),
        "pass_rows": len(passed),
        "failure_rows": len(failures),
        "missing_filter_summaries": max(expected - len(summary_paths), 0),
        "failure_rate_rows": float(len(failures)) / float(len(rows)) if rows else None,
        "top_csv": args.top_csv,
        "output_csv": args.output_csv,
    }
    Path(args.run_report_json).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))


if __name__ == "__main__":
    main()
