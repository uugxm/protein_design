#!/usr/bin/env python3
"""Build expression-ready candidate packages for epitope scaffold designs."""

import argparse
import csv
import json
import os
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from pdb_metrics import (
    BACKBONE_ATOMS,
    atom_lookup,
    kabsch_rmsd,
    map_motif_residues,
    read_motif_tsv,
    read_pdb_atoms,
    selected_atom_pairs,
)


PRIMARY_ORDER = ["design_1", "design_9", "design_4"]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: List[Dict[str, str]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def find_one(root: Path, pattern: str) -> Optional[Path]:
    hits = sorted([p for p in root.glob(pattern) if p.exists() and p.is_file()])
    return hits[0] if hits else None


def find_by_design(root: Path, design_id: str, suffix: str) -> Optional[Path]:
    hits = sorted([p for p in root.rglob(design_id + "*" + suffix) if p.exists() and p.is_file()])
    if not hits:
        return None
    hits.sort(key=lambda p: (0 if "predictions_flat" in p.parts else 1, len(str(p))))
    return hits[0]


def parse_job_name(path_text: str) -> str:
    if not path_text:
        return ""
    return Path(path_text).stem


def copy_if_exists(src: Optional[Path], dst: Path) -> str:
    if not src or not src.exists():
        return ""
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return str(dst)


def parse_mpnn_header(path: Optional[Path]) -> Dict[str, str]:
    if not path or not path.exists():
        return {}
    for raw in path.read_text(errors="ignore").splitlines():
        if raw.startswith(">") and "sample=" in raw:
            header = raw[1:]
            out = {"mpnn_header": header}
            for key in ("score", "global_score", "seq_recovery"):
                match = re.search(r"%s=([-+]?[0-9]*\.?[0-9]+)" % key, header)
                if match:
                    out["mpnn_" + key] = match.group(1)
            return out
    return {}


def fasta_sequence(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    chunks = []
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith(">"):
            chunks.append(line)
    return "".join(chunks)


def kabsch_transform(reference_coords: np.ndarray, model_coords: np.ndarray) -> Tuple[np.ndarray, np.ndarray]:
    ref = np.asarray(reference_coords, dtype=float)
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
    return rot, ref_centroid - np.dot(mob_centroid, rot)


def transform_coord(coord, rot, trans):
    return np.dot(np.asarray(coord, dtype=float), rot) + trans


def pdb_atom_line(serial: int, atom: Dict[str, object], coord, chain: str) -> str:
    atom_name = str(atom["atom"])[:4]
    resname = str(atom["resname"])[:3]
    element = str(atom.get("element") or atom_name[:1])[:2].upper()
    return (
        "ATOM  %5d %-4s %3s %1s%4d    %8.3f%8.3f%8.3f%6.2f%6.2f          %2s\n"
        % (
            serial,
            atom_name,
            resname,
            chain[:1],
            int(atom["resseq"]),
            float(coord[0]),
            float(coord[1]),
            float(coord[2]),
            1.0,
            float(atom.get("bfactor") or 0.0),
            element,
        )
    )


def write_minimal_cif_from_pdb(pdb_path: Path, out_path: Path, data_name: str) -> str:
    atoms = read_pdb_atoms(str(pdb_path)) if pdb_path.exists() else []
    if not atoms:
        return ""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as handle:
        handle.write("data_%s\n#\n" % re.sub(r"[^A-Za-z0-9_.-]+", "_", data_name))
        handle.write("loop_\n")
        columns = [
            "_atom_site.group_PDB", "_atom_site.id", "_atom_site.type_symbol",
            "_atom_site.label_atom_id", "_atom_site.label_alt_id",
            "_atom_site.label_comp_id", "_atom_site.label_asym_id",
            "_atom_site.label_seq_id", "_atom_site.pdbx_PDB_ins_code",
            "_atom_site.Cartn_x", "_atom_site.Cartn_y", "_atom_site.Cartn_z",
            "_atom_site.occupancy", "_atom_site.B_iso_or_equiv",
            "_atom_site.auth_seq_id", "_atom_site.auth_asym_id",
            "_atom_site.auth_atom_id", "_atom_site.auth_comp_id",
        ]
        for column in columns:
            handle.write(column + "\n")
        for idx, atom in enumerate(atoms, start=1):
            coord = atom["coord"]
            handle.write(
                "%s %d %s %s . %s %s %d . %.3f %.3f %.3f 1.00 %.2f %d %s %s %s\n"
                % (
                    atom["record"], idx, atom["element"], atom["atom"], atom["resname"],
                    atom["chain"], atom["resseq"], float(coord[0]), float(coord[1]), float(coord[2]),
                    float(atom.get("bfactor") or 0.0), atom["resseq"], atom["chain"], atom["atom"], atom["resname"],
                )
            )
        handle.write("#\n")
    return str(out_path)


def motif_only_aligned_pdb(reference_pdb: Path, motif_tsv: Path, models: Dict[str, Tuple[Path, Optional[Path]]], out_pdb: Path) -> Dict[str, object]:
    motif_ref = read_motif_tsv(str(motif_tsv))
    ref_atoms = read_pdb_atoms(str(reference_pdb))
    ref_lookup = atom_lookup(ref_atoms)
    reference_motif_atoms = []
    for chain, resseq in motif_ref:
        for atom in ref_atoms:
            if atom["chain"] == chain and atom["resseq"] == resseq and atom["atom"] in BACKBONE_ATOMS:
                reference_motif_atoms.append(atom)

    report = {"reference_motif_residues": ["%s%d" % item for item in motif_ref], "models": {}}
    out_pdb.parent.mkdir(parents=True, exist_ok=True)
    serial = 1
    with out_pdb.open("w") as handle:
        for atom in reference_motif_atoms:
            handle.write(pdb_atom_line(serial, atom, atom["coord"], "R"))
            serial += 1
        handle.write("TER\n")

        for chain_label, (model_pdb, trb_path) in models.items():
            if not model_pdb or not model_pdb.exists():
                report["models"][chain_label] = {"status": "missing_model"}
                continue
            try:
                ref_coords, model_coords, missing = selected_atom_pairs(
                    str(reference_pdb), str(model_pdb), str(motif_tsv), atom_names=BACKBONE_ATOMS, model_trb=str(trb_path) if trb_path else None
                )
                rmsd = kabsch_rmsd(ref_coords, model_coords)
                rot, trans = kabsch_transform(ref_coords, model_coords)
                model_motif = map_motif_residues(motif_ref, str(trb_path) if trb_path else None)
                model_atoms = read_pdb_atoms(str(model_pdb))
                wanted = set((chain, resseq) for chain, resseq in model_motif)
                for atom in model_atoms:
                    if (atom["chain"], atom["resseq"]) in wanted and atom["atom"] in BACKBONE_ATOMS:
                        handle.write(pdb_atom_line(serial, atom, transform_coord(atom["coord"], rot, trans), chain_label))
                        serial += 1
                handle.write("TER\n")
                report["models"][chain_label] = {
                    "status": "aligned",
                    "model_pdb": str(model_pdb),
                    "trb_path": str(trb_path) if trb_path else "",
                    "motif_rmsd": rmsd,
                    "motif_atoms_compared": int(len(ref_coords)),
                    "motif_atoms_missing": int(len(missing)),
                    "mapped_motif_residues": ["%s%d" % item for item in model_motif],
                }
            except Exception as exc:
                report["models"][chain_label] = {"status": "error", "error": repr(exc), "model_pdb": str(model_pdb)}
        handle.write("END\n")
    return report


def write_motif_mapping_tsv(path: Path, mapping_report: Dict[str, object]) -> None:
    rows = []
    ref = mapping_report.get("reference_motif_residues", [])
    for model_label, payload in mapping_report.get("models", {}).items():
        mapped = payload.get("mapped_motif_residues", []) if isinstance(payload, dict) else []
        for idx, ref_res in enumerate(ref):
            rows.append({
                "model": model_label,
                "reference_residue": ref_res,
                "model_residue": mapped[idx] if idx < len(mapped) else "",
            })
    write_csv(path, rows, ["model", "reference_residue", "model_residue"])


def write_pymol(path: Path, design_id: str, rels: Dict[str, str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "reinitialize",
        "load %s, reference_motif_aligned" % rels["motif_aligned"],
        "load %s, af3_model" % rels["af3_pdb"],
        "load %s, rf3_model" % rels["rf3_pdb"],
        "load %s, rfdiffusion_backbone" % rels["backbone_pdb"],
        "hide everything",
        "show cartoon, af3_model or rf3_model or rfdiffusion_backbone",
        "color gray80, af3_model",
        "color marine, rf3_model",
        "color wheat, rfdiffusion_backbone",
        "show sticks, reference_motif_aligned",
        "color yellow, reference_motif_aligned and chain R",
        "color orange, reference_motif_aligned and chain A",
        "color cyan, reference_motif_aligned and chain B",
        "select motif_reference, reference_motif_aligned and chain R",
        "select motif_af3_aligned, reference_motif_aligned and chain A",
        "select motif_rf3_aligned, reference_motif_aligned and chain B",
        "select local_support_af3, af3_model within 8 of motif_af3_aligned",
        "select local_support_rf3, rf3_model within 8 of motif_rf3_aligned",
        "show sticks, local_support_af3 or local_support_rf3",
        "set cartoon_transparency, 0.45, af3_model",
        "set cartoon_transparency, 0.35, rf3_model",
        "set stick_radius, 0.16",
        "zoom reference_motif_aligned, 12",
        "set ray_opaque_background, off",
        "png %s_motif_qc.png, width=1800, height=1200, ray=1" % design_id,
    ]
    path.write_text("\n".join(lines) + "\n")


def row_by_design(rows: Iterable[Dict[str, str]], key: str = "design_id") -> Dict[str, Dict[str, str]]:
    return {row.get(key, ""): row for row in rows if row.get(key)}


def consensus_by_design(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Dict[str, str]]]:
    out: Dict[str, Dict[str, Dict[str, str]]] = {}
    for row in rows:
        out.setdefault(row.get("design_id", ""), {})[row.get("predictor", "")] = row
    return out


def relpath(path: Path, start: Path) -> str:
    return os.path.relpath(path, start)


def make_package(args: argparse.Namespace) -> None:
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    reports_dir = out_dir / "reports"
    visualization_dir = out_dir / "visualization"
    reports_dir.mkdir(parents=True, exist_ok=True)
    visualization_dir.mkdir(parents=True, exist_ok=True)

    shortlist = row_by_design(read_csv(Path(args.shortlist_csv)))
    consensus = consensus_by_design(read_csv(Path(args.consensus_csv)))
    top_consensus = row_by_design(read_csv(Path(args.top_consensus_csv)))
    backend_root = Path(args.backend_root)
    cross_root = Path(args.cross_model_root)
    reference_pdb = Path(args.reference_pdb)
    motif_tsv = Path(args.motif_tsv)

    final_rows = []
    for rank, design_id in enumerate(PRIMARY_ORDER, start=1):
        design_dir = out_dir / design_id
        design_dir.mkdir(parents=True, exist_ok=True)
        package_paths = {}
        job_name = ""
        af3 = consensus.get(design_id, {}).get("af3", {})
        rf3 = consensus.get(design_id, {}).get("rf3", {})
        boltz = consensus.get(design_id, {}).get("boltz", {})
        shortlist_row = shortlist.get(design_id, {})
        top_row = top_consensus.get(design_id, {})

        canonical_fasta = find_one(cross_root / "canonical" / design_id / "fasta", "*.fasta")
        canonical_json = find_one(cross_root / "canonical" / design_id / "json", "*.json")
        canonical_cif = find_one(cross_root / "canonical" / design_id / "cif", "*.cif")
        if canonical_fasta:
            job_name = canonical_fasta.stem
        else:
            job_name = parse_job_name(rf3.get("model_output_path", ""))

        af3_pdb = backend_root / "array_work" / design_id / "predictions_flat" / (design_id + ".pdb")
        af3_json = backend_root / "array_work" / design_id / "predictions_flat" / (design_id + ".json")
        rf3_pdb = find_by_design(cross_root / "predictions_flat" / "rf3", design_id, ".pdb")
        rf3_cif = find_by_design(cross_root / "predictions_flat" / "rf3", design_id, ".cif")
        rf3_json = find_by_design(cross_root / "predictions_flat" / "rf3", design_id, ".json")
        rf3_trb = find_by_design(cross_root / "predictions_flat" / "rf3_mappings", design_id, ".trb")
        backbone_pdb = backend_root / "rfdiffusion_outputs" / (design_id + ".pdb")
        backbone_trb = backend_root / "rfdiffusion_outputs" / (design_id + ".trb")
        mpnn_fasta = backend_root / "array_work" / design_id / "mpnn_outputs" / "seqs" / (design_id + ".fa")

        package_paths["sequence_fasta"] = copy_if_exists(canonical_fasta, design_dir / (design_id + "_final_sequence.fasta"))
        package_paths["canonical_json"] = copy_if_exists(canonical_json, design_dir / (design_id + "_canonical_input.json"))
        package_paths["canonical_cif"] = copy_if_exists(canonical_cif, design_dir / (design_id + "_canonical_backbone.cif"))
        package_paths["af3_pdb"] = copy_if_exists(af3_pdb, design_dir / (design_id + "_af3_model.pdb"))
        package_paths["af3_cif"] = write_minimal_cif_from_pdb(af3_pdb, design_dir / (design_id + "_af3_model.cif"), design_id + "_af3_model")
        package_paths["af3_json"] = copy_if_exists(af3_json, design_dir / (design_id + "_af3_confidence.json"))
        package_paths["rf3_pdb"] = copy_if_exists(rf3_pdb, design_dir / (design_id + "_rf3_model.pdb"))
        package_paths["rf3_cif"] = copy_if_exists(rf3_cif, design_dir / (design_id + "_rf3_model.cif"))
        package_paths["rf3_json"] = copy_if_exists(rf3_json, design_dir / (design_id + "_rf3_confidence.json"))
        package_paths["backbone_pdb"] = copy_if_exists(backbone_pdb, design_dir / (design_id + "_rfdiffusion_backbone.pdb"))
        package_paths["backbone_trb"] = copy_if_exists(backbone_trb, design_dir / (design_id + "_rfdiffusion_mapping.trb"))
        package_paths["rf3_trb"] = copy_if_exists(rf3_trb, design_dir / (design_id + "_rf3_mapping.trb"))
        package_paths["mpnn_fasta"] = copy_if_exists(mpnn_fasta, design_dir / (design_id + "_proteinmpnn_all_sequences.fa"))

        motif_aligned = design_dir / (design_id + "_motif_only_aligned.pdb")
        alignment_report = motif_only_aligned_pdb(
            reference_pdb,
            motif_tsv,
            {
                "A": (af3_pdb, backbone_trb),
                "B": (rf3_pdb, rf3_trb or backbone_trb),
            },
            motif_aligned,
        )
        package_paths["motif_only_aligned_pdb"] = str(motif_aligned)
        mapping_tsv = design_dir / (design_id + "_motif_mapping.tsv")
        write_motif_mapping_tsv(mapping_tsv, alignment_report)
        package_paths["motif_mapping_tsv"] = str(mapping_tsv)

        pymol_path = visualization_dir / (design_id + "_motif_qc.pml")
        write_pymol(
            pymol_path,
            design_id,
            {
                "motif_aligned": relpath(motif_aligned, visualization_dir),
                "af3_pdb": relpath(design_dir / (design_id + "_af3_model.pdb"), visualization_dir),
                "rf3_pdb": relpath(design_dir / (design_id + "_rf3_model.pdb"), visualization_dir),
                "backbone_pdb": relpath(design_dir / (design_id + "_rfdiffusion_backbone.pdb"), visualization_dir),
            },
        )
        package_paths["pymol_script"] = str(pymol_path)

        mpnn = parse_mpnn_header(mpnn_fasta)
        sequence = fasta_sequence(canonical_fasta)
        priority = "high" if design_id in ("design_1", "design_9") else "medium"
        qc = {
            "design_id": design_id,
            "source_backend": "RFdiffusion v1",
            "job_name": job_name,
            "sequence_length": len(sequence),
            "proteinmpnn": mpnn,
            "af3": af3,
            "rf3": rf3,
            "boltz": boltz,
            "boltz_warning": top_row.get("boltz_warning", shortlist_row.get("Boltz warning", "")),
            "clusters": {
                "global_fold_cluster": shortlist_row.get("global_fold_cluster_id", ""),
                "motif_local_cluster": shortlist_row.get("motif_local_cluster_id", ""),
                "sequence_cluster": shortlist_row.get("sequence_cluster_id", ""),
            },
            "selection_reason": shortlist_row.get("selection_reason", ""),
            "recommended_experimental_priority": priority,
            "package_paths": package_paths,
            "motif_alignment": alignment_report,
        }
        qc_path = design_dir / (design_id + "_qc.json")
        qc_path.write_text(json.dumps(qc, indent=2, sort_keys=True) + "\n")

        summary = [
            "# %s Final Candidate Summary" % design_id,
            "",
            "- design_id: `%s`" % design_id,
            "- source backend: RFdiffusion v1",
            "- recommended experimental priority: `%s`" % priority,
            "- selection reason: %s" % shortlist_row.get("selection_reason", ""),
            "- global fold cluster: `%s`" % shortlist_row.get("global_fold_cluster_id", ""),
            "- motif-local cluster: `%s`" % shortlist_row.get("motif_local_cluster_id", ""),
            "- sequence cluster: `%s`" % shortlist_row.get("sequence_cluster_id", ""),
            "",
            "## ProteinMPNN",
            "",
            "- score: `%s`" % mpnn.get("mpnn_score", ""),
            "- global_score: `%s`" % mpnn.get("mpnn_global_score", ""),
            "- seq_recovery: `%s`" % mpnn.get("mpnn_seq_recovery", ""),
            "",
            "## Prediction QC",
            "",
            "| predictor | pass | pLDDT | PAE | motif RMSD | clash_count |",
            "| --- | --- | ---: | ---: | ---: | ---: |",
            "| AF3 | %s | %s | %s | %s | %s |" % (af3.get("pass", ""), af3.get("plddt_mean", ""), af3.get("pae_mean", ""), af3.get("motif_rmsd", ""), af3.get("clash_count", "")),
            "| RF3 | %s | %s | %s | %s | %s |" % (rf3.get("pass", ""), rf3.get("plddt_mean", ""), rf3.get("pae_mean", ""), rf3.get("motif_rmsd", ""), rf3.get("clash_count", "")),
            "",
            "## Boltz Warning",
            "",
            top_row.get("boltz_warning", shortlist_row.get("Boltz warning", "")) or "none",
            "",
            "## Files",
            "",
        ]
        for key, value in package_paths.items():
            summary.append("- %s: `%s`" % (key, value))
        summary_path = design_dir / (design_id + "_summary.md")
        summary_path.write_text("\n".join(summary) + "\n")

        final_rows.append({
            "rank": str(rank),
            "design_id": design_id,
            "tier": "primary",
            "expression_priority": priority,
            "AF3 pass": af3.get("pass", ""),
            "RF3 pass": rf3.get("pass", ""),
            "AF3 motif RMSD": af3.get("motif_rmsd", ""),
            "RF3 motif RMSD": rf3.get("motif_rmsd", ""),
            "AF3 pLDDT": af3.get("plddt_mean", ""),
            "RF3 pLDDT": rf3.get("plddt_mean", ""),
            "AF3 PAE": af3.get("pae_mean", ""),
            "RF3 PAE": rf3.get("pae_mean", ""),
            "fold_cluster": shortlist_row.get("global_fold_cluster_id", ""),
            "motif_local_cluster": shortlist_row.get("motif_local_cluster_id", ""),
            "sequence_cluster": shortlist_row.get("sequence_cluster_id", ""),
            "Boltz warning": top_row.get("boltz_warning", shortlist_row.get("Boltz warning", "")),
            "recommended_action": "small-scale expression and motif-binding QC",
        })

    fields = [
        "rank", "design_id", "tier", "expression_priority", "AF3 pass", "RF3 pass",
        "AF3 motif RMSD", "RF3 motif RMSD", "AF3 pLDDT", "RF3 pLDDT",
        "AF3 PAE", "RF3 PAE", "fold_cluster", "motif_local_cluster",
        "sequence_cluster", "Boltz warning", "recommended_action",
    ]
    write_csv(reports_dir / "final_expression_shortlist.csv", final_rows, fields)
    print("Packaged %d final candidates into %s" % (len(final_rows), out_dir))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--shortlist_csv", required=True)
    parser.add_argument("--consensus_csv", required=True)
    parser.add_argument("--top_consensus_csv", required=True)
    parser.add_argument("--backend_root", required=True)
    parser.add_argument("--cross_model_root", required=True)
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--out_dir", required=True)
    args = parser.parse_args()
    make_package(args)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
