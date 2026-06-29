#!/usr/bin/env python3
"""Prepare a reusable motif definition from a reference complex."""

import argparse
import csv
import json
import shutil
from pathlib import Path
from typing import Iterable, List, Tuple

from pdb_metrics import read_pdb_atoms
from validate_motif_definition import AA3_TO_1


def parse_ranges(text: str) -> List[Tuple[str, int, int]]:
    ranges = []
    for chunk in text.split(","):
        item = chunk.strip()
        if not item:
            continue
        chain = item[0]
        span = item[1:]
        if "-" in span:
            start, end = span.split("-", 1)
        else:
            start = end = span
        ranges.append((chain, int(start), int(end)))
    return ranges


def expand_ranges(ranges: Iterable[Tuple[str, int, int]]) -> List[Tuple[str, int]]:
    residues = []
    for chain, start, end in ranges:
        step = 1 if start <= end else -1
        for resseq in range(start, end + step, step):
            residues.append((chain, resseq))
    return residues


def residue_names(reference_pdb: Path):
    names = {}
    for atom in read_pdb_atoms(str(reference_pdb)):
        if atom["record"] == "ATOM":
            names.setdefault((atom["chain"], atom["resseq"]), atom["resname"])
    return names


def write_motif_tsv(path: Path, residues: List[Tuple[str, int]], names) -> str:
    sequence = []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["chain", "residue", "resname", "aa"], delimiter="\t")
        writer.writeheader()
        for chain, resseq in residues:
            resname = names.get((chain, resseq), "UNK")
            aa = AA3_TO_1.get(resname.upper(), "X")
            sequence.append(aa)
            writer.writerow({"chain": chain, "residue": resseq, "resname": resname, "aa": aa})
    return "".join(sequence)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complex_pdb", required=True, help="Input reference complex PDB.")
    parser.add_argument("--motif_ranges", required=True, help="Comma-separated motif ranges such as A163-181 or A163-170,A175-181.")
    parser.add_argument("--out_dir", required=True, help="Directory for motif_residues.tsv and manifest JSON.")
    parser.add_argument("--name", default="epitope_motif", help="Stable motif/job name used in output metadata.")
    parser.add_argument("--copy_reference", action="store_true", help="Copy the reference PDB into out_dir/reference.pdb.")
    parser.add_argument("--notes", default="", help="Optional free-text provenance note.")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    complex_pdb = Path(args.complex_pdb)
    residues = expand_ranges(parse_ranges(args.motif_ranges))
    names = residue_names(complex_pdb)
    motif_tsv = out_dir / "motif_residues.tsv"
    sequence = write_motif_tsv(motif_tsv, residues, names)

    reference_pdb = complex_pdb
    if args.copy_reference:
        reference_pdb = out_dir / "reference.pdb"
        shutil.copy2(complex_pdb, reference_pdb)

    missing = [{"chain": c, "residue": r} for c, r in residues if (c, r) not in names]
    manifest = {
        "schema": "protein_design.epitope_motif.v1",
        "name": args.name,
        "reference_pdb": str(reference_pdb.resolve()),
        "source_complex_pdb": str(complex_pdb.resolve()),
        "motif_tsv": str(motif_tsv.resolve()),
        "motif_ranges": args.motif_ranges,
        "motif_sequence": sequence,
        "motif_residue_count": len(residues),
        "missing_residues": missing,
        "notes": args.notes,
    }
    manifest_path = out_dir / "motif_definition.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifest, sort_keys=True))
    return 0 if not missing else 2


if __name__ == "__main__":
    raise SystemExit(main())
