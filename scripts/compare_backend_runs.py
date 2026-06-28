#!/usr/bin/env python3
"""Compare backend-level epitope scaffold runs after downstream filtering."""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean, median


METRICS = ["plddt_mean", "pae_mean", "motif_rmsd", "clash_count"]


def to_float(value):
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def read_csv(path):
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def read_run_report(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except Exception:
        return {}


def summarize_backend(name, run_dir):
    run_dir = Path(run_dir)
    rows = read_csv(run_dir / "reports" / "all_filter_summary.csv")
    top_rows = read_csv(run_dir / "reports" / "top_designs.csv")
    report = read_run_report(run_dir / "reports" / "run_report.json")
    backbone_count = len(list((run_dir / "rfdiffusion_outputs").glob("design_*.pdb")))
    mpnn_count = len(list((run_dir / "array_work").glob("*/mpnn_outputs/seqs/*.fa")))
    prediction_pdbs = list((run_dir / "array_work").glob("*/predictions_flat/*.pdb"))
    predicted_backbones = {path.parent.parent.name for path in prediction_pdbs}
    filter_count = len(list((run_dir / "array_work").glob("*/filter_summary.csv")))
    pass_rows = [row for row in rows if row.get("pass") == "PASS"]
    out = {
        "backend": name,
        "run_dir": str(run_dir),
        "backbone_pdbs": backbone_count,
        "expected_backbones": report.get("expected_backbones", backbone_count),
        "backbone_success_rate": safe_rate(backbone_count, report.get("expected_backbones", backbone_count)),
        "proteinmpnn_fastas": mpnn_count,
        "proteinmpnn_success_rate": safe_rate(mpnn_count, backbone_count),
        "prediction_pdbs": len(prediction_pdbs),
        "predicted_backbones": len(predicted_backbones),
        "af3_prediction_success_rate": safe_rate(len(predicted_backbones), backbone_count),
        "filter_summaries": filter_count,
        "filter_rows": len(rows),
        "filter_pass_rows": len(pass_rows),
        "filter_pass_rate": safe_rate(len(pass_rows), len(rows)),
        "top_design_id": top_rows[0].get("design_id", "") if top_rows else "",
        "top_backbone_id": top_rows[0].get("backbone_id", "") if top_rows else "",
        "top_pass": top_rows[0].get("pass", "") if top_rows else "",
    }
    for metric in METRICS:
        values = [to_float(row.get(metric)) for row in rows]
        values = [v for v in values if v is not None]
        out[f"{metric}_n"] = len(values)
        out[f"{metric}_mean"] = mean(values) if values else ""
        out[f"{metric}_median"] = median(values) if values else ""
        out[f"{metric}_min"] = min(values) if values else ""
        out[f"{metric}_max"] = max(values) if values else ""
        out[f"top_{metric}"] = top_rows[0].get(metric, "") if top_rows else ""
    return out


def safe_rate(numer, denom):
    try:
        denom = float(denom)
        return float(numer) / denom if denom else ""
    except Exception:
        return ""


def write_csv(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def write_markdown(path, rows):
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "backend", "backbone_success_rate", "proteinmpnn_success_rate",
        "af3_prediction_success_rate", "filter_pass_rate", "plddt_mean_mean",
        "pae_mean_mean", "motif_rmsd_mean", "clash_count_mean",
        "top_backbone_id", "top_design_id", "top_pass",
    ]
    with path.open("w") as handle:
        handle.write("# Backend Comparison\n\n")
        handle.write("| " + " | ".join(fields) + " |\n")
        handle.write("| " + " | ".join(["---"] * len(fields)) + " |\n")
        for row in rows:
            values = [format_value(row.get(field, "")) for field in fields]
            handle.write("| " + " | ".join(values) + " |\n")
        handle.write("\nRanking in each backend uses pLDDT descending, PAE ascending, motif RMSD ascending, and clash_count ascending.\n")


def format_value(value):
    if isinstance(value, float):
        return f"{value:.4f}"
    return str(value)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="append", required=True, help="name=run_dir; repeat for each backend.")
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--output_md", required=True)
    args = parser.parse_args()

    rows = []
    for item in args.backend:
        if "=" not in item:
            raise SystemExit("--backend must be name=run_dir")
        name, run_dir = item.split("=", 1)
        rows.append(summarize_backend(name, run_dir))

    write_csv(Path(args.output_csv), rows)
    write_markdown(Path(args.output_md), rows)
    print(json.dumps(rows, sort_keys=True))


if __name__ == "__main__":
    main()
