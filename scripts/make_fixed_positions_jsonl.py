#!/usr/bin/env python3
"""Create ProteinMPNN fixed-position JSONL files for RFdiffusion motifs.

ProteinMPNN expects one JSON object like:
{"design_name": {"A": [12, 13, 14], "B": []}}

The positions are 1-based chain positions in the parsed ProteinMPNN sequence,
not necessarily the original PDB residue numbers. For RFdiffusion outputs,
provide the matching ``.trb`` files so original motif residues can be mapped to
the generated scaffold residue numbers before converting to ProteinMPNN
positions.
"""

import argparse
import glob
import json
import os
import sys

from pdb_metrics import (
    load_rfdiffusion_trb_mapping,
    read_motif_tsv,
    read_pdb_atoms,
    residue_position_map,
)


def parse_extra_fixed(text):
    residues = []
    if not text:
        return residues
    for chunk in text.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            raise ValueError("extra fixed residue must look like A:12 or A:12-18: %s" % chunk)
        chain, spec = chunk.split(":", 1)
        if "-" in spec:
            start, end = [int(x) for x in spec.split("-", 1)]
            step = 1 if start <= end else -1
            for resseq in range(start, end + step, step):
                residues.append((chain, resseq))
        else:
            residues.append((chain, int(spec)))
    return residues


def find_trb_for_pdb(pdb_path, trb_dir):
    if not trb_dir:
        return None
    stem = os.path.splitext(os.path.basename(pdb_path))[0]
    candidates = [
        os.path.join(trb_dir, stem + ".trb"),
        os.path.splitext(pdb_path)[0] + ".trb",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    hits = glob.glob(os.path.join(trb_dir, "**", stem + ".trb"), recursive=True)
    return hits[0] if hits else None


def pdb_name(path):
    return os.path.splitext(os.path.basename(path))[0]


def chain_ids_from_atoms(atoms):
    chains = []
    seen = set()
    for atom in atoms:
        chain = atom["chain"]
        if chain not in seen:
            chains.append(chain)
            seen.add(chain)
    return chains


def fixed_positions_for_pdb(pdb_path, motif_residues, extra_residues, trb_path=None, strict=False):
    atoms = read_pdb_atoms(pdb_path)
    pos_map = residue_position_map(atoms)
    chains = chain_ids_from_atoms(atoms)
    fixed = {chain: [] for chain in chains}

    trb_mapping = load_rfdiffusion_trb_mapping(trb_path) if trb_path else {}
    missing = []
    for residue in motif_residues + extra_residues:
        mapped = trb_mapping.get(residue, residue)
        chain, resseq = mapped
        pos = pos_map.get((chain, resseq))
        if pos is None:
            missing.append({"original": residue, "mapped": mapped})
            continue
        fixed.setdefault(chain, []).append(pos)

    for chain in list(fixed):
        fixed[chain] = sorted(set(fixed[chain]))

    if missing and strict:
        raise RuntimeError("%s: motif residues not found after mapping: %s" % (pdb_path, missing))
    return fixed, missing


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--pdb_dir", required=True, help="Directory containing RFdiffusion backbone PDB files.")
    parser.add_argument("--motif_tsv", required=True, help="TSV with chain/start/end or chain/residue motif rows.")
    parser.add_argument("--output_jsonl", required=True, help="ProteinMPNN fixed_positions_jsonl output path.")
    parser.add_argument("--trb_dir", default="", help="Directory containing RFdiffusion .trb files; defaults to pdb_dir.")
    parser.add_argument("--extra_fixed", default="", help="Additional output-PDB residues to fix, e.g. A:3-8,B:11.")
    parser.add_argument("--strict", action="store_true", help="Fail if any motif residue cannot be mapped.")
    args = parser.parse_args()

    pdb_paths = sorted(glob.glob(os.path.join(args.pdb_dir, "*.pdb")))
    if not pdb_paths:
        raise SystemExit("no PDB files found in %s" % args.pdb_dir)

    motif_residues = read_motif_tsv(args.motif_tsv)
    extra_residues = parse_extra_fixed(args.extra_fixed)
    trb_dir = args.trb_dir or args.pdb_dir
    fixed_dict = {}
    warnings = []

    for path in pdb_paths:
        trb_path = find_trb_for_pdb(path, trb_dir)
        fixed, missing = fixed_positions_for_pdb(
            path,
            motif_residues,
            extra_residues,
            trb_path=trb_path,
            strict=args.strict,
        )
        fixed_dict[pdb_name(path)] = fixed
        if missing:
            warnings.append("%s: %d motif residues missing" % (pdb_name(path), len(missing)))

    out_dir = os.path.dirname(os.path.abspath(args.output_jsonl))
    if out_dir:
        os.makedirs(out_dir, exist_ok=True)
    with open(args.output_jsonl, "w") as handle:
        handle.write(json.dumps(fixed_dict, sort_keys=True) + "\n")

    for warning in warnings:
        sys.stderr.write("WARNING: %s\n" % warning)
    sys.stderr.write("Wrote fixed positions for %d PDBs to %s\n" % (len(fixed_dict), args.output_jsonl))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
