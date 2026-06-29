#!/usr/bin/env python3
"""Validate Foundry RFD3 motif-scaffolding JSON before submission."""

import argparse
import json
import re
from pathlib import Path
from typing import List, Tuple

from pdb_metrics import read_pdb_atoms


def parse_selection(text: str) -> List[Tuple[str, int]]:
    residues = []
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        match = re.match(r"^([A-Za-z_])(-?\d+)(?:-(-?\d+))?$", item)
        if not match:
            raise ValueError("cannot parse motif selection item %r" % item)
        chain, start_text, end_text = match.groups()
        start = int(start_text)
        end = int(end_text or start_text)
        step = 1 if start <= end else -1
        for resseq in range(start, end + step, step):
            residues.append((chain, resseq))
    return residues


def reference_residues(path: Path):
    return {(atom["chain"], atom["resseq"]) for atom in read_pdb_atoms(str(path)) if atom["record"] == "ATOM"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rfd3_json", required=True, help="Input JSON from make_rfd3_motif_input.py.")
    parser.add_argument("--out_json", default="", help="Optional validation report JSON path.")
    args = parser.parse_args()

    payload = json.loads(Path(args.rfd3_json).read_text())
    reports = []
    for name, spec in payload.items():
        errors = []
        input_path = Path(spec.get("input", ""))
        motif_selection = spec.get("extra", {}).get("motif_selection", "")
        fixed_atoms = spec.get("select_fixed_atoms", {})
        contig = spec.get("contig", "")
        residues = []
        try:
            residues = parse_selection(motif_selection)
        except Exception as exc:
            errors.append("invalid_motif_selection:%r" % (exc,))
        if not input_path.exists():
            errors.append("reference_input_missing")
        elif residues:
            present = reference_residues(input_path)
            missing = [{"chain": c, "residue": r} for c, r in residues if (c, r) not in present]
            if missing:
                errors.append("motif_residues_missing_from_reference")
        else:
            missing = []
        if not contig:
            errors.append("missing_contig")
        if motif_selection and motif_selection not in fixed_atoms and "select_unfixed_sequence" not in spec:
            errors.append("motif_selection_not_fixed_or_explicitly_unfixed")
        reports.append({
            "name": name,
            "status": "PASS" if not errors else "FAIL",
            "input": str(input_path),
            "contig": contig,
            "motif_selection": motif_selection,
            "motif_residue_count": len(residues),
            "missing_residues": missing if input_path.exists() and residues else [],
            "fixed_atoms": fixed_atoms,
            "errors": errors,
        })

    report = {"status": "PASS" if all(row["status"] == "PASS" for row in reports) else "FAIL", "inputs": reports}
    if args.out_json:
        out = Path(args.out_json)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
