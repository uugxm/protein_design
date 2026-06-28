#!/usr/bin/env python3
"""Collect confidence and geometry metrics for protein-design filtering."""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional

from pdb_metrics import count_clashes, mean_bfactor_plddt, motif_rmsd


def _mean_value(value: Any) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, list):
        vals = []  # type: List[float]
        stack = list(value)
        while stack:
            item = stack.pop()
            if isinstance(item, (int, float)):
                vals.append(float(item))
            elif isinstance(item, list):
                stack.extend(item)
        return mean(vals) if vals else None
    return None


def _get_any(payload: Dict[str, Any], keys: List[str]) -> Any:
    for key in keys:
        if key in payload:
            return payload[key]
    return None


def _normalize_plddt(value: Optional[float]) -> Optional[float]:
    if value is None:
        return None
    if 0.0 <= value <= 1.0:
        return value * 100.0
    return value


def parse_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        return {"confidence_file": str(path), "parse_error": repr(exc)}

    plddt = _normalize_plddt(_mean_value(_get_any(payload, ["plddt", "atom_plddts", "confidenceScore"])))
    ptm = _mean_value(_get_any(payload, ["ptm", "ptm_score", "predicted_tm_score", "chain_ptm"]))
    iptm = _mean_value(_get_any(payload, ["iptm", "iptm_score", "ranking_confidence"]))
    pae = _mean_value(_get_any(payload, ["pae", "predicted_aligned_error"]))
    ranking_score = _mean_value(_get_any(payload, ["ranking_score", "ranking_confidence"]))
    has_clash = _mean_value(_get_any(payload, ["has_clash"]))

    return {
        "confidence_file": str(path),
        "plddt_mean": plddt,
        "ptm": ptm,
        "iptm": iptm,
        "pae_mean": pae,
        "ranking_score": ranking_score,
        "prediction_has_clash": has_clash,
        "parse_error": "",
    }


def collect_json_metrics(input_dir: Optional[Path]) -> Dict[str, Dict[str, Any]]:
    metrics = {}
    if not input_dir:
        return metrics
    for path in sorted(input_dir.rglob("*.json")):
        lower_name = path.name.lower()
        if "manifest" in lower_name or lower_name.endswith("_input.json"):
            continue
        row = parse_json(path)
        stem = path.stem
        metrics[stem] = row
    return metrics


def collect_pdbs(pdb_dir: Optional[Path]) -> Dict[str, Path]:
    if not pdb_dir:
        return {}
    return {path.stem: path for path in sorted(pdb_dir.rglob("*.pdb"))}


def find_best_match(stem: str, candidates: Dict[str, Any]) -> Optional[str]:
    if stem in candidates:
        return stem
    for key in candidates:
        if stem in key or key in stem:
            return key
    return None


def find_trb(stem: str, trb_dir: Optional[Path]) -> Optional[str]:
    if not trb_dir:
        return None
    direct = trb_dir / (stem + ".trb")
    if direct.exists():
        return str(direct)
    for path in trb_dir.rglob(stem + ".trb"):
        return str(path)
    return None


def pass_fail(row: Dict[str, Any], args: argparse.Namespace) -> str:
    checks = []
    if args.min_plddt is not None and row.get("plddt_mean") is not None:
        checks.append(float(row["plddt_mean"]) >= args.min_plddt)
    if args.max_pae is not None and row.get("pae_mean") is not None:
        checks.append(float(row["pae_mean"]) <= args.max_pae)
    if args.max_motif_rmsd is not None and row.get("motif_rmsd") is not None:
        checks.append(float(row["motif_rmsd"]) <= args.max_motif_rmsd)
    if args.max_clashes is not None and row.get("clash_count") is not None:
        checks.append(int(row["clash_count"]) <= args.max_clashes)
    if not checks:
        return ""
    return "PASS" if all(checks) else "FAIL"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=False, help="Directory containing prediction JSON files.")
    parser.add_argument("--pdb_dir", required=False, help="Directory containing predicted/model PDB files.")
    parser.add_argument("--reference_pdb", required=False, help="Reference motif PDB for RMSD.")
    parser.add_argument("--motif_tsv", required=False, help="Motif TSV with chain/start/end or chain/residue.")
    parser.add_argument("--trb_dir", required=False, help="RFdiffusion .trb directory for model motif mapping.")
    parser.add_argument("--output_csv", required=True, help="Summary CSV to write.")
    parser.add_argument("--atom_names", default="N,CA,C,O", help="Comma-separated atom names for motif RMSD.")
    parser.add_argument("--clash_cutoff", type=float, default=2.0)
    parser.add_argument("--min_plddt", type=float, default=None)
    parser.add_argument("--max_pae", type=float, default=None)
    parser.add_argument("--max_motif_rmsd", type=float, default=None)
    parser.add_argument("--max_clashes", type=int, default=None)
    args = parser.parse_args()

    input_dir = Path(args.input_dir) if args.input_dir else None
    pdb_dir = Path(args.pdb_dir) if args.pdb_dir else None
    trb_dir = Path(args.trb_dir) if args.trb_dir else None
    json_metrics = collect_json_metrics(input_dir)
    pdbs = collect_pdbs(pdb_dir)
    design_ids = sorted(set(json_metrics) | set(pdbs))

    rows = []
    atom_names = [item.strip() for item in args.atom_names.split(",") if item.strip()]
    for design_id in design_ids:
        row = {
            "design_id": design_id,
            "confidence_file": "",
            "model_pdb": "",
            "plddt_mean": None,
            "ptm": None,
            "iptm": None,
            "pae_mean": None,
            "ranking_score": None,
            "prediction_has_clash": None,
            "motif_rmsd": None,
            "motif_atoms_compared": None,
            "motif_atoms_missing": None,
            "clash_count": None,
            "pass": "",
            "parse_error": "",
        }
        json_key = find_best_match(design_id, json_metrics)
        if json_key:
            row.update(json_metrics[json_key])
        pdb_key = find_best_match(design_id, pdbs)
        if pdb_key:
            pdb_path = pdbs[pdb_key]
            row["model_pdb"] = str(pdb_path)
            if row.get("plddt_mean") is None:
                row["plddt_mean"] = mean_bfactor_plddt(str(pdb_path))
            row["clash_count"] = count_clashes(str(pdb_path), cutoff=args.clash_cutoff)
            if args.reference_pdb and args.motif_tsv:
                try:
                    geom = motif_rmsd(
                        args.reference_pdb,
                        str(pdb_path),
                        args.motif_tsv,
                        atom_names=atom_names,
                        model_trb=find_trb(pdb_key, trb_dir),
                    )
                    row.update(geom)
                except Exception as exc:
                    row["parse_error"] = (row.get("parse_error") or "") + " geometry_error=%r" % (exc,)
        row["pass"] = pass_fail(row, args)
        rows.append(row)

    if not rows:
        rows = [{
            "design_id": "",
            "confidence_file": "",
            "model_pdb": "",
            "plddt_mean": None,
            "ptm": None,
            "iptm": None,
            "pae_mean": None,
            "ranking_score": None,
            "prediction_has_clash": None,
            "motif_rmsd": None,
            "motif_atoms_compared": None,
            "motif_atoms_missing": None,
            "clash_count": None,
            "pass": "",
            "parse_error": "no JSON or PDB inputs found",
        }]

    output = Path(args.output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "design_id", "confidence_file", "model_pdb", "plddt_mean", "ptm", "iptm",
        "pae_mean", "ranking_score", "prediction_has_clash",
        "motif_rmsd", "motif_atoms_compared", "motif_atoms_missing",
        "clash_count", "pass", "parse_error",
    ]
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
