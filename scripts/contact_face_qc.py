#!/usr/bin/env python3
"""Lightweight motif contact-face QC for designed scaffold structures."""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional

from pre_order_qc import local_support_count, motif_sasa_proxy


def find_trb(stem: str, trb_dir: Optional[Path]) -> Optional[Path]:
    if not trb_dir:
        return None
    direct = trb_dir / (stem + ".trb")
    if direct.exists():
        return direct
    hits = sorted(trb_dir.rglob(stem + "*.trb"))
    return hits[0] if hits else None


def status(row: Dict[str, object], min_support: int, min_accessible_fraction: float) -> str:
    if str(row.get("motif_sasa_note", "")).endswith("not_found"):
        return "FAIL"
    if int(row["local_support_residue_count"]) < min_support:
        return "FAIL"
    frac_text = str(row.get("motif_sasa_accessible_fraction", ""))
    if frac_text and float(frac_text) < min_accessible_fraction:
        return "WARN"
    return "PASS"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pdb_dir", required=True, help="Directory containing model/backbone PDB files.")
    parser.add_argument("--motif_tsv", required=True, help="Reference motif TSV.")
    parser.add_argument("--trb_dir", default="", help="Optional RFdiffusion .trb mapping directory.")
    parser.add_argument("--output_csv", required=True, help="QC table to write.")
    parser.add_argument("--output_json", default="", help="Optional JSON report path.")
    parser.add_argument("--support_radius", type=float, default=8.0, help="CA distance cutoff for local support residue count.")
    parser.add_argument("--min_support_residues", type=int, default=8, help="Minimum non-motif residues near motif CA atoms.")
    parser.add_argument("--min_accessible_fraction", type=float, default=0.20, help="Warn below this motif exposure proxy fraction.")
    args = parser.parse_args()

    pdb_dir = Path(args.pdb_dir)
    trb_dir = Path(args.trb_dir) if args.trb_dir else None
    rows: List[Dict[str, object]] = []
    for pdb_path in sorted(pdb_dir.rglob("*.pdb")):
        trb = find_trb(pdb_path.stem, trb_dir)
        exposure = motif_sasa_proxy(pdb_path, Path(args.motif_tsv), trb)
        row = {
            "design_id": pdb_path.stem,
            "model_pdb": str(pdb_path),
            "trb_path": str(trb or ""),
            "local_support_residue_count": local_support_count(pdb_path, Path(args.motif_tsv), trb, radius=args.support_radius),
            "motif_sasa_proxy_a2": exposure["motif_sasa_proxy_a2"],
            "motif_sasa_accessible_fraction": exposure["motif_sasa_accessible_fraction"],
            "motif_sasa_note": exposure["motif_sasa_note"],
        }
        row["contact_face_status"] = status(row, args.min_support_residues, args.min_accessible_fraction)
        rows.append(row)

    if not rows:
        rows.append({
            "design_id": "", "model_pdb": "", "trb_path": "", "local_support_residue_count": 0,
            "motif_sasa_proxy_a2": "", "motif_sasa_accessible_fraction": "", "motif_sasa_note": "no_pdb_inputs_found",
            "contact_face_status": "FAIL",
        })
    out = Path(args.output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "design_id", "model_pdb", "trb_path", "local_support_residue_count",
        "motif_sasa_proxy_a2", "motif_sasa_accessible_fraction", "motif_sasa_note", "contact_face_status",
    ]
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    if args.output_json:
        Path(args.output_json).write_text(json.dumps({"rows": rows}, indent=2, sort_keys=True) + "\n")
    return 0 if any(row["contact_face_status"] in ("PASS", "WARN") for row in rows) else 2


if __name__ == "__main__":
    raise SystemExit(main())
