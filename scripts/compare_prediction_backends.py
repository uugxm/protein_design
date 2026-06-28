#!/usr/bin/env python3
"""Merge AF3/RF3/Boltz filter summaries into a long consensus table."""

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Dict, List, Optional, Tuple


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


def read_design_map(path: str) -> Dict[str, str]:
    mapping = {}
    if not path:
        return mapping
    with Path(path).open("r", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            job_name = row.get("job_name", "")
            design_id = row.get("design_id", "")
            if job_name and design_id:
                mapping[job_name] = design_id
            if design_id:
                mapping[design_id] = design_id
    return mapping


def normalize_design_id(raw_id: str, design_map: Dict[str, str]) -> str:
    if raw_id in design_map:
        return design_map[raw_id]
    for job_name, design_id in design_map.items():
        if job_name and (raw_id.startswith(job_name) or job_name.startswith(raw_id)):
            return design_id
    return raw_id


def load_inputs(specs: List[str]) -> List[Dict[str, str]]:
    rows = []
    for spec in specs:
        if "=" not in spec:
            raise SystemExit("--filter_summary entries must be predictor=/path/to/filter_summary.csv")
        predictor, path = spec.split("=", 1)
        rows.extend(read_filter(Path(path), predictor))
    return rows


def fmt(value: Optional[float]) -> str:
    return "" if value is None else "%.6g" % value


def prediction_status(row: Dict[str, str]) -> str:
    if not row:
        return "MISSING"
    if row.get("model_pdb") or row.get("confidence_file"):
        return "SUCCESS"
    if row.get("parse_error"):
        return "FAILED"
    return "MISSING"


def normalize_row(design_id: str, predictor: str, row: Dict[str, str]) -> Dict[str, str]:
    plddt = to_float(row.get("plddt_mean"))
    pae = to_float(row.get("pae_mean"))
    motif = to_float(row.get("motif_rmsd"))
    ptm = to_float(row.get("ptm"))
    iptm = to_float(row.get("iptm"))
    ranking = to_float(row.get("ranking_score"))
    confidence = plddt
    if confidence is None:
        confidence = ranking if ranking is not None else ptm
    return {
        "design_id": design_id,
        "predictor": predictor,
        "prediction_status": prediction_status(row),
        "pass": row.get("pass", "") if row else "",
        "plddt_mean": fmt(plddt),
        "confidence_score": fmt(confidence),
        "ptm": fmt(ptm),
        "iptm": fmt(iptm),
        "pae_mean": fmt(pae),
        "ranking_score": fmt(ranking),
        "motif_rmsd": fmt(motif),
        "motif_atoms_compared": row.get("motif_atoms_compared", "") if row else "",
        "motif_atoms_missing": row.get("motif_atoms_missing", "") if row else "",
        "clash_count": row.get("clash_count", "") if row else "",
        "model_output_path": row.get("model_pdb", "") if row else "",
        "confidence_file": row.get("confidence_file", "") if row else "",
        "parse_error": row.get("parse_error", "") if row else "",
    }


def summarize(grouped: Dict[str, Dict[str, Dict[str, str]]]) -> Tuple[Dict, str]:
    predictors = ["af3", "rf3", "boltz"]
    by_predictor = {}
    for predictor in predictors:
        rows = [by_pred.get(predictor, {}) for by_pred in grouped.values()]
        by_predictor[predictor] = {
            "total_designs": len(rows),
            "success": sum(1 for row in rows if prediction_status(row) == "SUCCESS"),
            "pass": sum(1 for row in rows if row.get("pass") == "PASS"),
            "failed": sum(1 for row in rows if prediction_status(row) == "FAILED"),
            "missing": sum(1 for row in rows if prediction_status(row) == "MISSING"),
        }

    all_three_motif_pass = []
    high_confidence_consensus = []
    af3_only_positive = []
    model_conflicts = []
    for design_id, by_pred in sorted(grouped.items()):
        passes = {p: by_pred.get(p, {}).get("pass") == "PASS" for p in predictors}
        successes = {p: prediction_status(by_pred.get(p, {})) == "SUCCESS" for p in predictors}
        if all(passes.values()):
            all_three_motif_pass.append(design_id)
        if all(successes.values()) and all(passes.values()):
            high_confidence_consensus.append(design_id)
        if passes["af3"] and not (passes["rf3"] or passes["boltz"]):
            af3_only_positive.append(design_id)
        if passes["af3"] and any(successes[p] and not passes[p] for p in ("rf3", "boltz")):
            model_conflicts.append(design_id)

    summary = {
        "predictors": by_predictor,
        "rf3_success_count": by_predictor["rf3"]["success"],
        "boltz_success_count": by_predictor["boltz"]["success"],
        "all_three_motif_rmsd_pass_count": len(all_three_motif_pass),
        "all_three_motif_rmsd_pass_designs": all_three_motif_pass,
        "high_confidence_consensus_designs": high_confidence_consensus,
        "af3_only_positive_designs": af3_only_positive,
        "model_conflict_designs": model_conflicts,
    }
    lines = [
        "# Cross-Model Prediction Summary",
        "",
        "| predictor | success | pass | failed | missing |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for predictor in predictors:
        item = by_predictor[predictor]
        lines.append(
            "| %s | %d | %d | %d | %d |"
            % (predictor, item["success"], item["pass"], item["failed"], item["missing"])
        )
    lines.extend([
        "",
        "- RF3 successful predictions: %d" % summary["rf3_success_count"],
        "- Boltz successful predictions: %d" % summary["boltz_success_count"],
        "- AF3/RF3/Boltz motif RMSD all pass: %d" % summary["all_three_motif_rmsd_pass_count"],
        "- High-confidence consensus designs: %s" % (", ".join(high_confidence_consensus) or "none"),
        "- AF3-only positives to downgrade: %s" % (", ".join(af3_only_positive) or "none"),
        "- Model-conflict designs: %s" % (", ".join(model_conflicts) or "none"),
        "",
    ])
    return summary, "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--filter_summary", action="append", default=[], help="predictor=/path/to/filter_summary.csv")
    parser.add_argument("--canonical_manifest", default="", help="Optional canonical manifest TSV mapping job_name to design_id.")
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--summary_json", default="")
    parser.add_argument("--summary_md", default="")
    args = parser.parse_args()

    rows = load_inputs(args.filter_summary)
    design_map = read_design_map(args.canonical_manifest)
    grouped: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in rows:
        design_id = normalize_design_id(row.get("design_id") or row.get("backbone_id") or "", design_map)
        predictor = row["predictor"]
        grouped.setdefault(design_id, {})[predictor] = row

    out_rows = []
    for design_id, by_predictor in sorted(grouped.items()):
        for predictor in ("af3", "rf3", "boltz"):
            out_rows.append(normalize_row(design_id, predictor, by_predictor.get(predictor, {})))

    fieldnames = [
        "design_id", "predictor", "prediction_status", "pass",
        "plddt_mean", "confidence_score", "ptm", "iptm", "pae_mean", "ranking_score",
        "motif_rmsd", "motif_atoms_compared", "motif_atoms_missing", "clash_count",
        "model_output_path", "confidence_file", "parse_error",
    ]
    out_path = Path(args.output_csv)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(out_rows)
    summary, summary_md = summarize(grouped)
    if args.summary_json:
        summary_path = Path(args.summary_json)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    if args.summary_md:
        md_path = Path(args.summary_md)
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_path.write_text(summary_md + "\n")
    print("Wrote consensus summary with %d rows to %s" % (len(out_rows), out_path))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
