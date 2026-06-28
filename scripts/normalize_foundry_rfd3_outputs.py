#!/usr/bin/env python3
"""Normalize Foundry RFD3 outputs for the shared epitope-scaffold pipeline."""

import argparse
import gzip
import json
import shutil
import tempfile
from pathlib import Path


def load_structure(path):
    from biotite.structure.io.pdbx import CIFFile, get_structure

    path = Path(path)
    if path.suffix == ".gz":
        with gzip.open(path, "rt") as handle:
            text = handle.read()
        with tempfile.NamedTemporaryFile("w", suffix=".cif", delete=False) as tmp:
            tmp.write(text)
            tmp_path = Path(tmp.name)
        try:
            cif = CIFFile.read(str(tmp_path))
        finally:
            tmp_path.unlink(missing_ok=True)
    else:
        cif = CIFFile.read(str(path))
    return get_structure(cif, model=1, include_bonds=False)


def write_pdb(atom_array, path):
    from biotite.structure.io.pdb import PDBFile

    pdb = PDBFile()
    pdb.set_structure(atom_array)
    pdb.write(str(path))


def candidate_structures(input_dir):
    input_dir = Path(input_dir)
    paths = []
    for pattern in ["*.cif.gz", "*.cif", "*.pdb", "*.pdb.gz"]:
        paths.extend(input_dir.glob(pattern))
    out = []
    for path in sorted(paths):
        name = path.name
        if "_denoised_model_" in name or "_noisy_model_" in name:
            continue
        out.append(path)
    return out


def copy_metadata(structure_path, out_path):
    name = structure_path.name
    for suffix in [".cif.gz", ".pdb.gz", ".cif", ".pdb"]:
        if name.endswith(suffix):
            stem = name[: -len(suffix)]
            break
    else:
        stem = structure_path.stem
    meta = structure_path.with_name(stem + ".json")
    if meta.exists():
        shutil.copyfile(meta, out_path)
        return meta
    return None


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--max_designs", type=int, default=0)
    parser.add_argument("--strict_mapping", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    structures = candidate_structures(args.input_dir)
    if args.max_designs:
        structures = structures[: args.max_designs]
    if not structures:
        raise SystemExit("no Foundry RFD3 structure outputs found in %s" % args.input_dir)

    manifest = []
    for idx, source in enumerate(structures):
        target = out_dir / ("design_%d.pdb" % idx)
        if source.name.endswith(".pdb"):
            shutil.copyfile(source, target)
        else:
            atom_array = load_structure(source)
            write_pdb(atom_array, target)
        meta_target = out_dir / ("design_%d.foundry_metadata.json" % idx)
        copied_meta = copy_metadata(source, meta_target)
        manifest.append({
            "design_id": "design_%d" % idx,
            "source_structure": str(source),
            "normalized_pdb": str(target),
            "source_metadata": str(copied_meta) if copied_meta else "",
            "normalized_metadata": str(meta_target) if copied_meta else "",
        })

    manifest_path = out_dir / "foundry_output_map.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")

    from make_motif_mapping_from_sequence import find_exact_sequence, motif_sequence, write_mapping

    ref_residues, seq = motif_sequence(args.reference_pdb, args.motif_tsv)
    failures = []
    for item in manifest:
        pdb_path = Path(item["normalized_pdb"])
        hits = find_exact_sequence(str(pdb_path), seq)
        if len(hits) != 1:
            failures.append("%s: expected one motif hit for %s, found %d" % (pdb_path.name, seq, len(hits)))
            continue
        _chain, _start, model_residues = hits[0]
        write_mapping(pdb_path.with_suffix(".trb"), ref_residues, model_residues)

    if failures:
        for failure in failures:
            print("WARNING: " + failure)
        if args.strict_mapping:
            raise SystemExit("failed motif mapping for %d outputs" % len(failures))

    print("normalized_foundry_outputs=%d" % len(manifest))


if __name__ == "__main__":
    main()
