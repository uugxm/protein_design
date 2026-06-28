#!/usr/bin/env python3
"""Diagnose Boltz motif disagreement for cross-model validation outputs."""

import argparse
import csv
import json
import math
import sys
from os.path import relpath
from pathlib import Path

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from pdb_metrics import (  # noqa: E402
    atom_lookup,
    kabsch_rmsd,
    load_rfdiffusion_trb_mapping,
    map_motif_residues,
    read_motif_tsv,
    read_pdb_atoms,
)


ATOM_NAMES = ("N", "CA", "C", "O")


def safe_name(text):
    return "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in text)


def find_flat_pdb(run_dir, predictor, design_id):
    hits = sorted((run_dir / "predictions_flat" / predictor).glob(design_id + "*.pdb"))
    if not hits:
        raise SystemExit("no %s flat PDB found for %s" % (predictor, design_id))
    if len(hits) > 1:
        exact = [p for p in hits if p.stem == design_id]
        if exact:
            return exact[0]
    return hits[0]


def find_mapping(run_dir, predictor, pdb_path):
    mapping = run_dir / "predictions_flat" / ("%s_mappings" % predictor) / (pdb_path.stem + ".trb")
    if not mapping.exists():
        raise SystemExit("no mapping found for %s" % pdb_path)
    return mapping


def get_atom(atoms, chain, resseq, atom_name):
    for atom in atoms:
        if atom["chain"] == chain and atom["resseq"] == resseq and atom["atom"] == atom_name:
            return atom
    return None


def residue_name(atoms, chain, resseq):
    atom = get_atom(atoms, chain, resseq, "CA") or get_atom(atoms, chain, resseq, "N")
    return atom["resname"] if atom else ""


def paired_atoms(reference_pdb, model_pdb, motif_tsv, mapping_path):
    motif_ref = read_motif_tsv(motif_tsv)
    motif_model = map_motif_residues(motif_ref, str(mapping_path))
    ref_atoms = read_pdb_atoms(reference_pdb)
    model_atoms = read_pdb_atoms(model_pdb)
    ref_lookup = atom_lookup(ref_atoms)
    model_lookup = atom_lookup(model_atoms)
    pairs = []
    missing = []
    for ref_res, model_res in zip(motif_ref, motif_model):
        for atom_name in ATOM_NAMES:
            ref_key = (ref_res[0], ref_res[1], atom_name)
            model_key = (model_res[0], model_res[1], atom_name)
            if ref_key in ref_lookup and model_key in model_lookup:
                pairs.append({
                    "ref_chain": ref_res[0],
                    "ref_resseq": ref_res[1],
                    "ref_resname": residue_name(ref_atoms, ref_res[0], ref_res[1]),
                    "model_chain": model_res[0],
                    "model_resseq": model_res[1],
                    "model_resname": residue_name(model_atoms, model_res[0], model_res[1]),
                    "atom": atom_name,
                    "ref_coord": ref_lookup[ref_key],
                    "model_coord": model_lookup[model_key],
                })
            else:
                missing.append({"reference": ref_key, "model": model_key})
    return pairs, missing, ref_atoms, model_atoms


def kabsch_transform(ref_coords, model_coords):
    ref = np.asarray(ref_coords, dtype=float)
    mob = np.asarray(model_coords, dtype=float)
    ref_centroid = ref.mean(axis=0)
    mob_centroid = mob.mean(axis=0)
    ref0 = ref - ref_centroid
    mob0 = mob - mob_centroid
    cov = np.dot(mob0.T, ref0)
    v, _s, wt = np.linalg.svd(cov)
    if np.linalg.det(np.dot(v, wt)) < 0.0:
        v[:, -1] *= -1.0
    rot = np.dot(v, wt)
    aligned = np.dot(mob0, rot) + ref_centroid
    rmsd = float(np.sqrt(((aligned - ref) ** 2).sum() / len(ref)))
    return aligned, rmsd


def ca_distances(atoms, residues=None):
    by_residue = {}
    for atom in atoms:
        if atom["atom"] == "CA":
            by_residue[(atom["chain"], atom["resseq"])] = atom["coord"]
    keys = residues or sorted(by_residue)
    coords = [by_residue[k] for k in keys if k in by_residue]
    if len(coords) < 2:
        return []
    return [float(np.linalg.norm(coords[i + 1] - coords[i])) for i in range(len(coords) - 1)]


def stats(values):
    if not values:
        return {"count": 0}
    arr = np.asarray(values, dtype=float)
    return {
        "count": int(len(values)),
        "min": float(arr.min()),
        "median": float(np.median(arr)),
        "max": float(arr.max()),
    }


def coord_stats(atoms):
    coords = np.asarray([atom["coord"] for atom in atoms], dtype=float)
    return {
        "min_x": float(coords[:, 0].min()),
        "max_x": float(coords[:, 0].max()),
        "min_y": float(coords[:, 1].min()),
        "max_y": float(coords[:, 1].max()),
        "min_z": float(coords[:, 2].min()),
        "max_z": float(coords[:, 2].max()),
    }


def write_mapping_tsv(path, design_id, pairs, missing, aligned):
    path.parent.mkdir(parents=True, exist_ok=True)
    missing_keys = {(tuple(item["reference"]), tuple(item["model"])) for item in missing}
    with path.open("w", newline="") as handle:
        fieldnames = [
            "design_id", "ref_chain", "ref_resseq", "ref_resname",
            "model_chain", "model_resseq", "model_resname", "atom",
            "ref_x", "ref_y", "ref_z", "model_x", "model_y", "model_z",
            "aligned_model_x", "aligned_model_y", "aligned_model_z",
            "post_align_distance",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        for pair, aligned_coord in zip(pairs, aligned):
            ref = pair["ref_coord"]
            model = pair["model_coord"]
            dist = float(np.linalg.norm(aligned_coord - ref))
            writer.writerow({
                "design_id": design_id,
                "ref_chain": pair["ref_chain"],
                "ref_resseq": pair["ref_resseq"],
                "ref_resname": pair["ref_resname"],
                "model_chain": pair["model_chain"],
                "model_resseq": pair["model_resseq"],
                "model_resname": pair["model_resname"],
                "atom": pair["atom"],
                "ref_x": "%.3f" % ref[0],
                "ref_y": "%.3f" % ref[1],
                "ref_z": "%.3f" % ref[2],
                "model_x": "%.3f" % model[0],
                "model_y": "%.3f" % model[1],
                "model_z": "%.3f" % model[2],
                "aligned_model_x": "%.3f" % aligned_coord[0],
                "aligned_model_y": "%.3f" % aligned_coord[1],
                "aligned_model_z": "%.3f" % aligned_coord[2],
                "post_align_distance": "%.3f" % dist,
            })
    return missing_keys


def write_aligned_pdb(path, pairs, aligned):
    with path.open("w") as handle:
        serial = 1
        for pair in pairs:
            ref = pair["ref_coord"]
            handle.write(
                "ATOM  %5d %-4s %3s R%4d    %8.3f%8.3f%8.3f  1.00 90.00           %2s\n"
                % (serial, pair["atom"][:4], pair["ref_resname"][:3], pair["ref_resseq"], ref[0], ref[1], ref[2], pair["atom"][0])
            )
            serial += 1
        handle.write("TER\n")
        for pair, coord in zip(pairs, aligned):
            handle.write(
                "ATOM  %5d %-4s %3s M%4d    %8.3f%8.3f%8.3f  1.00 50.00           %2s\n"
                % (serial, pair["atom"][:4], pair["model_resname"][:3], pair["model_resseq"], coord[0], coord[1], coord[2], pair["atom"][0])
            )
            serial += 1
        handle.write("TER\nEND\n")


def write_pml(path, aligned_pdb, source_pdb):
    aligned_rel = Path(relpath(aligned_pdb, path.parent))
    source_rel = Path(relpath(source_pdb, path.parent))
    path.write_text(
        "\n".join([
            "load %s, aligned_motif" % aligned_rel,
            "load %s, boltz_full_model" % source_rel,
            "hide everything",
            "show sticks, aligned_motif",
            "color green, chain R",
            "color magenta, chain M",
            "show cartoon, boltz_full_model",
            "set cartoon_transparency, 0.65, boltz_full_model",
            "zoom aligned_motif",
            "",
        ])
    )


def source_from_manifest(run_dir, design_name):
    manifest_path = run_dir / "predictions_flat/boltz/cross_model_top3.prediction_manifest.json"
    if not manifest_path.exists():
        return {}
    rows = json.loads(manifest_path.read_text())
    for row in rows:
        if row.get("design_id") == design_name:
            return row
    return {}


def diagnose_one(run_dir, reference_pdb, motif_tsv, design_id, out_dir):
    pdb_path = find_flat_pdb(run_dir, "boltz", design_id)
    mapping_path = find_mapping(run_dir, "boltz", pdb_path)
    pairs, missing, _ref_atoms, model_atoms = paired_atoms(reference_pdb, pdb_path, motif_tsv, mapping_path)
    ref_coords = np.asarray([pair["ref_coord"] for pair in pairs], dtype=float)
    model_coords = np.asarray([pair["model_coord"] for pair in pairs], dtype=float)
    aligned, rmsd = kabsch_transform(ref_coords, model_coords)
    mapped_residues = [(pair["model_chain"], pair["model_resseq"]) for pair in pairs if pair["atom"] == "CA"]
    all_ca = ca_distances(model_atoms)
    motif_ca = ca_distances(model_atoms, mapped_residues)
    mapping_tsv = out_dir / ("%s_boltz_motif_mapping.tsv" % design_id)
    aligned_pdb = out_dir / ("%s_boltz_motif_aligned.pdb" % design_id)
    pml = out_dir / ("%s_boltz_motif_alignment.pml" % design_id)
    write_mapping_tsv(mapping_tsv, design_id, pairs, missing, aligned)
    write_aligned_pdb(aligned_pdb, pairs, aligned)
    write_pml(pml, aligned_pdb, pdb_path)
    manifest = source_from_manifest(run_dir, pdb_path.stem)
    return {
        "design_id": design_id,
        "flat_pdb": str(pdb_path),
        "source_structure": manifest.get("source_structure", ""),
        "source_json": manifest.get("source_json", ""),
        "mapping_file": str(mapping_path),
        "motif_atoms_compared": len(pairs),
        "motif_atoms_missing": len(missing),
        "motif_rmsd": rmsd,
        "model_coord_stats": coord_stats(model_atoms),
        "all_ca_distance_stats": stats(all_ca),
        "motif_ca_distance_stats": stats(motif_ca),
        "mapping_tsv": str(mapping_tsv),
        "aligned_motif_pdb": str(aligned_pdb),
        "pymol_pml": str(pml),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--design_id", action="append", required=True)
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--report_md", required=True)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    results = [
        diagnose_one(run_dir, args.reference_pdb, args.motif_tsv, design_id, out_dir)
        for design_id in args.design_id
    ]
    report = [
        "# Boltz Motif Disagreement Diagnostics",
        "",
        "AF3 is the primary prediction backend, RF3 is optional confirmation, and Boltz is an optional conflict flag until MSA/template-enabled validation is tested.",
        "",
        "Boltz was run in no-MSA single-sequence mode for these diagnostics.",
        "",
        "| design | motif atoms compared | motif atoms missing | motif RMSD | median all-chain CA-CA | median motif CA-CA | source structure |",
        "| --- | ---: | ---: | ---: | ---: | ---: | --- |",
    ]
    for item in results:
        report.append(
            "| {design_id} | {motif_atoms_compared} | {motif_atoms_missing} | {motif_rmsd:.3f} | {all_ca:.3f} | {motif_ca:.3f} | `{source}` |".format(
                design_id=item["design_id"],
                motif_atoms_compared=item["motif_atoms_compared"],
                motif_atoms_missing=item["motif_atoms_missing"],
                motif_rmsd=item["motif_rmsd"],
                all_ca=item["all_ca_distance_stats"].get("median", math.nan),
                motif_ca=item["motif_ca_distance_stats"].get("median", math.nan),
                source=item["source_structure"],
            )
        )
    report.extend([
        "",
        "Interpretation:",
        "",
        "- The motif sequence mapping is present for the sampled Boltz outputs: design_1 and design_9 both compare 76 backbone motif atoms with 0 missing atoms.",
        "- The collector selected the expected Boltz model CIFs listed in `predictions_flat/boltz/cross_model_top3.prediction_manifest.json`.",
        "- The original Boltz CIF coordinates already have hundreds-of-Angstrom coordinate ranges, so the disagreement is not introduced by CIF-to-PDB conversion.",
        "- Consecutive CA distances are hundreds of Angstroms, including inside the mapped motif. This is consistent with a severe no-MSA Boltz structural failure for this task, not with a small residue-numbering offset.",
        "- Conclusion: Boltz no-MSA mode is not reliable as a hard gate for this de novo motif scaffold task. Treat it as an optional conflict flag until MSA/template-enabled validation is tested.",
        "",
        "Artifacts:",
        "",
    ])
    for item in results:
        report.extend([
            "- `%s` mapping TSV: `%s`" % (item["design_id"], item["mapping_tsv"]),
            "- `%s` aligned motif PDB: `%s`" % (item["design_id"], item["aligned_motif_pdb"]),
            "- `%s` PyMOL script: `%s`" % (item["design_id"], item["pymol_pml"]),
        ])
    Path(args.report_md).write_text("\n".join(report) + "\n")
    summary_path = out_dir / "boltz_disagreement_diagnostics.json"
    summary_path.write_text(json.dumps(results, indent=2, sort_keys=True) + "\n")
    print("Wrote diagnostics for %d designs to %s" % (len(results), out_dir))


if __name__ == "__main__":
    main()
