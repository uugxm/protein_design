#!/usr/bin/env python3
"""Create an RFdiffusion3/Foundry motif-scaffolding input JSON.

RFD3 uses Foundry's InputSpecification format. This helper intentionally writes
that format directly instead of translating RFdiffusion v1 slash contigs.
"""

import argparse
import json
from pathlib import Path

from pdb_metrics import read_motif_tsv, read_pdb_atoms


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def residue_sequence(pdb_path, residues):
    atoms = read_pdb_atoms(pdb_path)
    by_residue = {}
    for atom in atoms:
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"])
        by_residue.setdefault(key, atom["resname"])
    seq = []
    missing = []
    for chain, resseq in residues:
        resname = by_residue.get((chain, resseq))
        if resname is None:
            missing.append("%s%d" % (chain, resseq))
            seq.append("X")
        else:
            seq.append(AA3_TO_1.get(resname.upper(), "X"))
    return "".join(seq), missing


def collapse_residue_ranges(residues):
    if not residues:
        return []
    ranges = []
    start_chain, start_res = residues[0]
    prev_chain, prev_res = residues[0]
    for chain, resseq in residues[1:]:
        if chain == prev_chain and resseq == prev_res + 1:
            prev_res = resseq
            continue
        ranges.append((start_chain, start_res, prev_res))
        start_chain, start_res = chain, resseq
        prev_chain, prev_res = chain, resseq
    ranges.append((start_chain, start_res, prev_res))
    return ranges


def range_to_rfd3_text(chain, start, end):
    if start == end:
        return "%s%d" % (chain, start)
    return "%s%d-%d" % (chain, start, end)


def motif_selection(residues):
    return ",".join(range_to_rfd3_text(*item) for item in collapse_residue_ranges(residues))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference_pdb", required=True, help="Reference PDB/CIF path used by Foundry RFD3.")
    parser.add_argument("--motif_tsv", required=True, help="TSV with chain/start/end or chain/residue motif rows.")
    parser.add_argument("--output", required=True, help="Output RFD3 JSON path.")
    parser.add_argument("--metadata_out", default="", help="Optional motif mapping metadata JSON path.")
    parser.add_argument("--run_params_out", default="", help="Optional run_params JSON path.")
    parser.add_argument("--name", default="motif_scaffold", help="Top-level RFD3 input key.")
    parser.add_argument("--nterm_range", default="10-40", help="Designed N-terminal scaffold segment, e.g. 10-40.")
    parser.add_argument("--cterm_range", default="10-40", help="Designed C-terminal scaffold segment, e.g. 10-40.")
    parser.add_argument("--fixed_atoms", default="BKBN", help="Atoms to fix for motif residues: BKBN, ALL, TIP, or explicit names.")
    parser.add_argument("--unfix_motif_sequence", action="store_true", help="Allow motif sequence redesign.")
    parser.add_argument("--is_non_loopy", action="store_true", help="Set RFD3 is_non_loopy=True.")
    parser.add_argument("--length", default="", help="Optional total length constraint, e.g. 80-120.")
    parser.add_argument("--dialect", type=int, default=2)
    args = parser.parse_args()

    motif_residues = read_motif_tsv(args.motif_tsv)
    if not motif_residues:
        raise SystemExit("no motif residues read from %s" % args.motif_tsv)
    motif_text = motif_selection(motif_residues)
    contig = ",".join([args.nterm_range, motif_text, args.cterm_range])
    seq, missing = residue_sequence(args.reference_pdb, motif_residues)
    if missing:
        raise SystemExit("reference motif residues missing: %s" % ",".join(missing))

    spec = {
        "dialect": args.dialect,
        "input": str(Path(args.reference_pdb).expanduser().resolve()),
        "contig": contig,
        "select_fixed_atoms": {motif_text: args.fixed_atoms},
        "extra": {
            "motif_selection": motif_text,
            "motif_sequence": seq,
            "motif_source": str(Path(args.motif_tsv).expanduser().resolve()),
        },
    }
    if args.is_non_loopy:
        spec["is_non_loopy"] = True
    if args.length:
        spec["length"] = args.length
    if args.unfix_motif_sequence:
        spec["select_unfixed_sequence"] = motif_text

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({args.name: spec}, indent=2, sort_keys=True) + "\n")

    metadata = {
        "backend": "foundry_rfd3",
        "input_name": args.name,
        "reference_pdb": spec["input"],
        "motif_tsv": str(Path(args.motif_tsv).expanduser().resolve()),
        "motif_residues": [{"chain": c, "resseq": r} for c, r in motif_residues],
        "motif_selection": motif_text,
        "motif_sequence": seq,
        "contig": contig,
        "fixed_atoms": args.fixed_atoms,
    }
    for path_text in [args.metadata_out, args.run_params_out]:
        if path_text:
            path = Path(path_text)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(metadata, indent=2, sort_keys=True) + "\n")

    print(json.dumps(metadata, sort_keys=True))


if __name__ == "__main__":
    main()
