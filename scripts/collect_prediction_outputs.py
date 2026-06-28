#!/usr/bin/env python3
"""Collect predictor outputs into flat JSON/PDB/CIF files for filtering."""

import argparse
import json
import os
import re
import shutil
import shlex
import gzip
from pathlib import Path


def safe_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "design"


def first_existing(paths):
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def choose_json(root):
    patterns = [
        "**/*confidences*.json",
        "**/*confidence*.json",
        "**/*summary*.json",
        "**/*scores*.json",
        "**/*.score",
        "**/ranking*.json",
        "**/*.json",
    ]
    for pattern in patterns:
        hits = [
            p for p in sorted(root.glob(pattern))
            if "input" not in p.name.lower() and p.is_file()
        ]
        if hits:
            return hits[0]
    return None


def choose_structure(root):
    for pattern in ("**/*model*.cif", "**/*model*.cif.gz", "**/*.cif", "**/*.cif.gz", "**/*.pdb"):
        hits = [p for p in sorted(root.glob(pattern)) if p.is_file()]
        if hits:
            return hits[0]
    return None


def copy_json_like(json_path, flat_json):
    if json_path.suffix.lower() == ".score":
        payload = {"score_file": str(json_path), "raw_score": json_path.read_text(errors="ignore")}
        flat_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")
        return "wrapped_score_as_json"
    shutil.copy2(json_path, flat_json)
    return "copied_json"


def cif_tokens(line):
    return shlex.split(line, comments=False, posix=True)


def parse_cif_atom_site(cif_path):
    if str(cif_path).endswith(".gz"):
        with gzip.open(cif_path, "rt", errors="ignore") as handle:
            lines = handle.read().splitlines()
    else:
        lines = cif_path.read_text(errors="ignore").splitlines()
    atoms = []
    i = 0
    while i < len(lines):
        if lines[i].strip() != "loop_":
            i += 1
            continue
        i += 1
        columns = []
        while i < len(lines) and lines[i].strip().startswith("_"):
            columns.append(lines[i].strip())
            i += 1
        if not columns or not any(col.startswith("_atom_site.") for col in columns):
            continue
        col_index = {col: idx for idx, col in enumerate(columns)}
        while i < len(lines):
            line = lines[i].strip()
            if not line or line == "#" or line == "loop_" or line.startswith("_") or line.startswith("data_"):
                break
            parts = cif_tokens(line)
            if len(parts) < len(columns):
                i += 1
                continue
            def get(*names, default=""):
                for name in names:
                    idx = col_index.get(name)
                    if idx is not None and idx < len(parts):
                        value = parts[idx]
                        if value not in (".", "?"):
                            return value
                return default
            group = get("_atom_site.group_PDB", default="ATOM")
            atom = get("_atom_site.auth_atom_id", "_atom_site.label_atom_id", default="X")
            resname = get("_atom_site.auth_comp_id", "_atom_site.label_comp_id", default="UNK")
            chain = get("_atom_site.auth_asym_id", "_atom_site.label_asym_id", default="A")
            resseq = get("_atom_site.auth_seq_id", "_atom_site.label_seq_id", default="1")
            x = float(get("_atom_site.Cartn_x", default="0"))
            y = float(get("_atom_site.Cartn_y", default="0"))
            z = float(get("_atom_site.Cartn_z", default="0"))
            occ = float(get("_atom_site.occupancy", default="1"))
            bfac = float(get("_atom_site.B_iso_or_equiv", default="0"))
            element = get("_atom_site.type_symbol", default=atom[0])
            try:
                resseq_int = int(float(resseq))
            except ValueError:
                resseq_int = 1
            atoms.append((group, atom, resname, chain, resseq_int, x, y, z, occ, bfac, element))
            i += 1
    return atoms


def write_pdb_from_atoms(atoms, out_path):
    with out_path.open("w") as handle:
        for idx, atom in enumerate(atoms, start=1):
            group, atom_name, resname, chain, resseq, x, y, z, occ, bfac, element = atom
            record = "HETATM" if group.upper().startswith("HET") else "ATOM"
            handle.write(
                "%-6s%5d %-4s %3s %1s%4d    %8.3f%8.3f%8.3f%6.2f%6.2f          %2s\n"
                % (record, idx, atom_name[:4], resname[:3], chain[:1], resseq, x, y, z, occ, bfac, element[:2])
            )
        handle.write("END\n")


def convert_structure_to_pdb(structure_path, out_pdb):
    if structure_path.suffix.lower() == ".pdb":
        shutil.copy2(structure_path, out_pdb)
        return "copied_pdb"
    atoms = parse_cif_atom_site(structure_path)
    if not atoms:
        raise RuntimeError("no _atom_site records found in %s" % structure_path)
    write_pdb_from_atoms(atoms, out_pdb)
    return "converted_cif_to_pdb"


def collect_one(job_root, out_dir, flat_id, predictor):
    json_path = choose_json(job_root)
    structure_path = choose_structure(job_root)
    manifest = {
        "predictor": predictor,
        "design_id": flat_id,
        "source_json": str(json_path) if json_path else "",
        "source_structure": str(structure_path) if structure_path else "",
        "flat_json": "",
        "flat_pdb": "",
        "flat_cif": "",
    }

    if json_path:
        flat_json = out_dir / (flat_id + ".json")
        manifest["json_action"] = copy_json_like(json_path, flat_json)
        manifest["flat_json"] = str(flat_json)
    if structure_path:
        if ".cif" in "".join(structure_path.suffixes).lower():
            flat_cif = out_dir / (flat_id + ".cif")
            if str(structure_path).endswith(".gz"):
                with gzip.open(structure_path, "rb") as src, flat_cif.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            else:
                shutil.copy2(structure_path, flat_cif)
            manifest["flat_cif"] = str(flat_cif)
        flat_pdb = out_dir / (flat_id + ".pdb")
        manifest["structure_action"] = convert_structure_to_pdb(structure_path, flat_pdb)
        manifest["flat_pdb"] = str(flat_pdb)
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--predictor", default="af3", choices=["af3", "rf3", "boltz"])
    parser.add_argument("--input_dir", required=True, help="Raw predictor output directory.")
    parser.add_argument("--out_dir", required=True, help="Flat output directory for filter_designs.py.")
    parser.add_argument("--design_id", required=True)
    args = parser.parse_args()

    root = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    design_id = safe_name(args.design_id)

    job_roots = [p for p in sorted(root.iterdir()) if p.is_dir()]
    if not job_roots:
        job_roots = [root]

    manifests = []
    for idx, job_root in enumerate(job_roots, start=1):
        flat_id = design_id if len(job_roots) == 1 else safe_name(job_root.name)
        if flat_id in [item["design_id"] for item in manifests]:
            flat_id = "%s_%d" % (flat_id, idx)
        manifest = collect_one(job_root, out_dir, flat_id, args.predictor)
        manifests.append(manifest)

    manifest_path = out_dir / (design_id + ".prediction_manifest.json")
    manifest_path.write_text(json.dumps(manifests, indent=2, sort_keys=True) + "\n")
    print(json.dumps(manifests, sort_keys=True))
    bad = [m for m in manifests if not m["source_json"] or not m["source_structure"]]
    if bad:
        raise SystemExit("prediction output incomplete for %d/%d jobs" % (len(bad), len(manifests)))


if __name__ == "__main__":
    main()
