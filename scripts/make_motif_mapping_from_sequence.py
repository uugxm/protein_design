#!/usr/bin/env python3
"""Infer motif residue mappings from exact motif sequence in generated PDBs."""

import argparse
from pathlib import Path

import numpy as np

from pdb_metrics import read_motif_tsv, read_pdb_atoms


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def residues_from_atoms(atoms):
    residues = []
    seen = set()
    for atom in atoms:
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"], atom["icode"])
        if key in seen:
            continue
        seen.add(key)
        residues.append({
            "chain": atom["chain"],
            "resseq": atom["resseq"],
            "icode": atom["icode"],
            "resname": atom["resname"],
            "aa": AA3_TO_1.get(atom["resname"].upper(), "X"),
        })
    return residues


def motif_sequence(reference_pdb, motif_tsv):
    motif = read_motif_tsv(motif_tsv)
    residues = residues_from_atoms(read_pdb_atoms(reference_pdb))
    by_id = {(r["chain"], r["resseq"]): r for r in residues}
    seq = []
    for chain, resseq in motif:
        residue = by_id.get((chain, resseq))
        if residue is None:
            raise RuntimeError("reference motif residue not found: %s%d" % (chain, resseq))
        seq.append(residue["aa"])
    return motif, "".join(seq)


def find_exact_sequence(model_pdb, sequence):
    residues = residues_from_atoms(read_pdb_atoms(model_pdb))
    by_chain = {}
    for residue in residues:
        by_chain.setdefault(residue["chain"], []).append(residue)
    hits = []
    for chain, chain_residues in by_chain.items():
        chain_seq = "".join(r["aa"] for r in chain_residues)
        start = chain_seq.find(sequence)
        while start != -1:
            hits.append((chain, start, chain_residues[start:start + len(sequence)]))
            start = chain_seq.find(sequence, start + 1)
    return hits


def write_mapping(path, ref_residues, model_residues):
    con_ref = np.array([(chain, int(resseq)) for chain, resseq in ref_residues], dtype=object)
    con_hal = np.array(
        [(residue["chain"], int(residue["resseq"])) for residue in model_residues],
        dtype=object,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("wb") as handle:
        np.savez(handle, con_ref_pdb_idx=con_ref, con_hal_pdb_idx=con_hal)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--pdb_dir", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--strict", action="store_true")
    args = parser.parse_args()

    ref_residues, seq = motif_sequence(args.reference_pdb, args.motif_tsv)
    pdb_paths = sorted(Path(args.pdb_dir).glob("*.pdb"))
    if not pdb_paths:
        raise SystemExit("no PDB files found in %s" % args.pdb_dir)

    failures = []
    for pdb_path in pdb_paths:
        hits = find_exact_sequence(str(pdb_path), seq)
        if len(hits) != 1:
            failures.append("%s: expected exactly one motif sequence hit for %s, found %d" % (pdb_path.name, seq, len(hits)))
            continue
        _chain, _start, model_residues = hits[0]
        out_path = Path(args.out_dir) / (pdb_path.stem + ".trb")
        write_mapping(out_path, ref_residues, model_residues)
        print("%s\t%s\t%s" % (pdb_path.name, seq, out_path))

    if failures:
        for failure in failures:
            print("WARNING: " + failure)
        if args.strict:
            raise SystemExit("failed to infer motif mapping for %d PDBs" % len(failures))


if __name__ == "__main__":
    main()
