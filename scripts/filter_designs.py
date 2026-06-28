#!/usr/bin/env python3
"""Collect lightweight protein-design filtering metrics from prediction outputs.

The script is intentionally conservative: it extracts common confidence fields
from AF2/AF3/Boltz-style JSON/NPZ outputs when present, and emits placeholders
for geometry metrics that require project-specific target/motif definitions.
"""

import argparse
import csv
import json
from pathlib import Path
from statistics import mean
from typing import Any, Dict, List, Optional


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


def parse_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text())
    except Exception as exc:
        return {"file": str(path), "parse_error": repr(exc)}

    plddt = _mean_value(_get_any(payload, ["plddt", "atom_plddts", "confidenceScore"]))
    ptm = _mean_value(_get_any(payload, ["ptm", "ptm_score", "predicted_tm_score"]))
    iptm = _mean_value(_get_any(payload, ["iptm", "iptm_score", "ranking_confidence"]))
    pae = _mean_value(_get_any(payload, ["pae", "predicted_aligned_error"]))

    return {
        "file": str(path),
        "plddt_mean": plddt,
        "ptm": ptm,
        "iptm": iptm,
        "pae_mean": pae,
        "interface_pae": None,
        "motif_rmsd": None,
        "clash_count": None,
        "interface_contacts": None,
        "parse_error": "",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="Directory containing prediction JSON files.")
    parser.add_argument("--output_csv", required=True, help="Summary CSV to write.")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    rows = [parse_json(path) for path in sorted(input_dir.rglob("*.json"))]
    if not rows:
        rows = [{
            "file": "",
            "plddt_mean": None,
            "ptm": None,
            "iptm": None,
            "pae_mean": None,
            "interface_pae": None,
            "motif_rmsd": None,
            "clash_count": None,
            "interface_contacts": None,
            "parse_error": "no JSON files found",
        }]

    output = Path(args.output_csv)
    output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
