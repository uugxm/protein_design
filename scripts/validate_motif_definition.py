#!/usr/bin/env python3
"""Validate and normalize an epitope/motif residue definition."""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Tuple

from pdb_metrics import BACKBONE_ATOMS, read_motif_tsv, read_pdb_atoms


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M",
}


def residue_index(reference_pdb: Path) -> Dict[Tuple[str, int], Dict[str, object]]:
    index: Dict[Tuple[str, int], Dict[str, object]] = {}
    for atom in read_pdb_atoms(str(reference_pdb)):
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"])
        entry = index.setdefault(key, {"resname": atom["resname"], "atoms": set()})
        entry["atoms"].add(atom["atom"])
    return index


def write_normalized_tsv(path: Path, residues: List[Tuple[str, int]], index: Dict[Tuple[str, int], Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chain", "residue", "resname", "aa"], delimiter="\t")
        writer.writeheader()
        for chain, resseq in residues:
            resname = str(index[(chain, resseq)]["resname"])
            writer.writerow({"chain": chain, "residue": resseq, "resname": resname, "aa": AA3_TO_1.get(resname.upper(), "X")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--reference_pdb", required=True, help="Reference PDB containing the motif residues.")
    parser.add_argument("--motif_tsv", required=True, help="Motif TSV with chain/residue or chain/start/end columns.")
    parser.add_argument("--out_json", default="", help="Optional validation report JSON path.")
    parser.add_argument("--normalized_tsv", default="", help="Optional one-residue-per-row normalized TSV path.")
    parser.add_argument("--require_backbone_atoms", default=",".join(BACKBONE_ATOMS), help="Comma-separated atom names required for each motif residue.")
    parser.add_argument("--min_residues", type=int, default=1, help="Minimum allowed number of motif residues.")
    args = parser.parse_args()

    residues = read_motif_tsv(args.motif_tsv)
    index = residue_index(Path(args.reference_pdb))
    required_atoms = [item.strip() for item in args.require_backbone_atoms.split(",") if item.strip()]
    missing_residues = []
    missing_atoms = []
    sequence = []

    for chain, resseq in residues:
        entry = index.get((chain, resseq))
        if not entry:
            missing_residues.append({"chain": chain, "residue": resseq})
            sequence.append("X")
            continue
        sequence.append(AA3_TO_1.get(str(entry["resname"]).upper(), "X"))
        for atom_name in required_atoms:
            if atom_name not in entry["atoms"]:
                missing_atoms.append({"chain": chain, "residue": resseq, "atom": atom_name})

    errors = []
    if len(residues) < args.min_residues:
        errors.append("motif_has_fewer_than_%d_residues" % args.min_residues)
    if missing_residues:
        errors.append("motif_residues_missing_from_reference")
    if missing_atoms:
        errors.append("required_atoms_missing_from_motif_residues")

    report = {
        "status": "PASS" if not errors else "FAIL",
        "reference_pdb": str(Path(args.reference_pdb).resolve()),
        "motif_tsv": str(Path(args.motif_tsv).resolve()),
        "motif_residue_count": len(residues),
        "motif_sequence": "".join(sequence),
        "motif_residues": [{"chain": chain, "residue": resseq} for chain, resseq in residues],
        "required_atoms": required_atoms,
        "missing_residues": missing_residues,
        "missing_atoms": missing_atoms,
        "errors": errors,
    }

    if args.normalized_tsv and report["status"] == "PASS":
        write_normalized_tsv(Path(args.normalized_tsv), residues, index)
        report["normalized_tsv"] = str(Path(args.normalized_tsv).resolve())
    if args.out_json:
        path = Path(args.out_json)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    return 0 if report["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
