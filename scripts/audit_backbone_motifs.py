#!/usr/bin/env python3
"""Audit generated backbone motif geometry before sequence design or prediction."""

import argparse
import csv
import json
import math
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from pdb_metrics import (  # noqa: E402
    BACKBONE_ATOMS,
    atom_lookup,
    kabsch_rmsd,
    load_rfdiffusion_trb_mapping,
    read_motif_tsv,
    read_pdb_atoms,
    squared_distance,
)


FIELDS = [
    "backend",
    "design_id",
    "raw_backbone_pdb",
    "raw_source_structure",
    "trb_path",
    "raw_backbone_motif_rmsd",
    "motif_atoms_compared",
    "motif_atoms_missing",
    "motif_residue_count",
    "motif_residues_mapped",
    "motif_residue_mapping_status",
    "local_support_residue_count",
    "backbone_length",
    "raw_backbone_clash_count_around_motif",
    "output_normalization_status",
    "normalization_metadata",
]


def natural_key(path: Path) -> Tuple:
    parts = re.split(r"(\d+)", path.stem)
    return tuple(int(p) if p.isdigit() else p for p in parts)


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return "%.6g" % value
    return str(value)


def parse_backend_specs(specs: Sequence[str]) -> Dict[str, Path]:
    out: Dict[str, Path] = {}
    for spec in specs:
        if "=" not in spec:
            raise SystemExit("Expected --backend name=/path/to/run_dir, got %s" % spec)
        name, path = spec.split("=", 1)
        out[name] = Path(path).resolve()
    return out


def read_foundry_map(run_dir: Path) -> Dict[str, Dict[str, str]]:
    candidates = [
        run_dir / "rfdiffusion_outputs" / "foundry_output_map.json",
        run_dir / "foundry_output_map.json",
    ]
    for path in candidates:
        if not path.exists():
            continue
        payload = json.loads(path.read_text())
        if isinstance(payload, list):
            return {str(item.get("design_id", "")): item for item in payload}
    return {}


def backbone_output_dir(run_dir: Path) -> Path:
    out = run_dir / "rfdiffusion_outputs"
    return out if out.exists() else run_dir


def unique_residues(atoms: Iterable[Dict[str, object]]) -> List[Tuple[str, int, str]]:
    seen = []
    found = set()
    for atom in atoms:
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"], atom["icode"])
        if key not in found:
            seen.append(key)
            found.add(key)
    return seen


def mapping_for(trb_path: Optional[Path]) -> Dict[Tuple[str, int], Tuple[str, int]]:
    if not trb_path or not trb_path.exists():
        return {}
    return load_rfdiffusion_trb_mapping(str(trb_path))


def mapped_motif_residues(
    motif_ref: Sequence[Tuple[str, int]], trb_path: Optional[Path]
) -> Tuple[List[Optional[Tuple[str, int]]], str]:
    mapping = mapping_for(trb_path)
    if mapping:
        mapped = [mapping.get(item) for item in motif_ref]
        present = sum(1 for item in mapped if item is not None)
        if present == len(motif_ref):
            return mapped, "complete"
        return mapped, "partial_%d_of_%d" % (present, len(motif_ref))
    if trb_path and trb_path.exists():
        return list(motif_ref), "trb_without_parseable_mapping_identity_fallback"
    return list(motif_ref), "no_trb_identity_mapping"


def motif_rmsd_from_mapping(
    reference_pdb: Path,
    model_pdb: Path,
    motif_ref: Sequence[Tuple[str, int]],
    motif_model: Sequence[Optional[Tuple[str, int]]],
    atom_names: Sequence[str],
) -> Dict[str, object]:
    ref_lookup = atom_lookup(read_pdb_atoms(str(reference_pdb)))
    model_lookup = atom_lookup(read_pdb_atoms(str(model_pdb)))
    ref_coords = []
    model_coords = []
    missing = 0
    for ref_res, model_res in zip(motif_ref, motif_model):
        ref_chain, ref_resseq = ref_res
        if model_res is None:
            missing += len(atom_names)
            continue
        model_chain, model_resseq = model_res
        for atom_name in atom_names:
            ref_key = (ref_chain, ref_resseq, atom_name)
            model_key = (model_chain, model_resseq, atom_name)
            if ref_key in ref_lookup and model_key in model_lookup:
                ref_coords.append(ref_lookup[ref_key])
                model_coords.append(model_lookup[model_key])
            else:
                missing += 1
    rmsd = kabsch_rmsd(ref_coords, model_coords) if len(ref_coords) >= 3 else None
    return {
        "raw_backbone_motif_rmsd": rmsd,
        "motif_atoms_compared": len(ref_coords),
        "motif_atoms_missing": missing,
    }


def heavy_atoms(atoms: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return [
        atom for atom in atoms
        if atom["record"] == "ATOM" and atom["element"] != "H" and atom["atom"] != "H"
    ]


def local_support_count(atoms: List[Dict[str, object]], motif_residues: Sequence[Optional[Tuple[str, int]]], cutoff: float) -> int:
    motif_set = {item for item in motif_residues if item is not None}
    motif_atoms = [atom for atom in heavy_atoms(atoms) if (atom["chain"], atom["resseq"]) in motif_set]
    if not motif_atoms:
        return 0
    cutoff2 = cutoff * cutoff
    support = set()
    for atom in heavy_atoms(atoms):
        residue = (atom["chain"], atom["resseq"])
        if residue in motif_set:
            continue
        for motif_atom in motif_atoms:
            if squared_distance(atom["coord"], motif_atom["coord"]) <= cutoff2:
                support.add(residue)
                break
    return len(support)


def local_clash_count(
    atoms: List[Dict[str, object]],
    motif_residues: Sequence[Optional[Tuple[str, int]]],
    neighborhood_cutoff: float,
    clash_cutoff: float,
) -> int:
    motif_set = {item for item in motif_residues if item is not None}
    motif_atoms = [atom for atom in heavy_atoms(atoms) if (atom["chain"], atom["resseq"]) in motif_set]
    if not motif_atoms:
        return 0
    neighborhood2 = neighborhood_cutoff * neighborhood_cutoff
    local_atoms = []
    for atom in heavy_atoms(atoms):
        residue = (atom["chain"], atom["resseq"])
        if residue in motif_set:
            local_atoms.append(atom)
            continue
        if any(squared_distance(atom["coord"], m["coord"]) <= neighborhood2 for m in motif_atoms):
            local_atoms.append(atom)
    clash2 = clash_cutoff * clash_cutoff
    clashes = 0
    for idx, a in enumerate(local_atoms):
        for b in local_atoms[idx + 1:]:
            if a["chain"] == b["chain"] and abs(a["resseq"] - b["resseq"]) <= 1:
                continue
            if squared_distance(a["coord"], b["coord"]) < clash2:
                clashes += 1
    return clashes


def normalization_status(backend: str, design_id: str, pdb_path: Path, trb_path: Optional[Path], foundry_map: Dict[str, Dict[str, str]]) -> Tuple[str, str, str]:
    foundry_item = foundry_map.get(design_id, {})
    if foundry_item:
        normalized = Path(foundry_item.get("normalized_pdb", ""))
        status = "foundry_normalized"
        if normalized and normalized.name != pdb_path.name:
            status = "foundry_normalized_name_mismatch"
        if not trb_path or not trb_path.exists():
            status += "_missing_trb"
        return status, foundry_item.get("source_structure", ""), foundry_item.get("normalized_metadata", "")
    if backend == "foundry_rfd3":
        return "foundry_map_missing", "", ""
    if trb_path and trb_path.exists():
        return "native_rfdiffusion_trb", "", ""
    return "native_or_unknown_no_trb", "", ""


def audit_backend(
    backend: str,
    run_dir: Path,
    reference_pdb: Path,
    motif_tsv: Path,
    atom_names: Sequence[str],
    support_cutoff: float,
    clash_neighborhood_cutoff: float,
    clash_cutoff: float,
) -> List[Dict[str, str]]:
    motif_ref = read_motif_tsv(str(motif_tsv))
    out_dir = backbone_output_dir(run_dir)
    foundry_map = read_foundry_map(run_dir)
    rows = []
    for pdb_path in sorted(out_dir.glob("design_*.pdb"), key=natural_key):
        design_id = pdb_path.stem
        trb_path = pdb_path.with_suffix(".trb")
        mapped, mapping_status = mapped_motif_residues(motif_ref, trb_path if trb_path.exists() else None)
        atoms = read_pdb_atoms(str(pdb_path))
        rmsd = motif_rmsd_from_mapping(reference_pdb, pdb_path, motif_ref, mapped, atom_names)
        norm_status, raw_source, norm_meta = normalization_status(
            backend, design_id, pdb_path, trb_path if trb_path.exists() else None, foundry_map
        )
        rows.append({
            "backend": backend,
            "design_id": design_id,
            "raw_backbone_pdb": str(pdb_path),
            "raw_source_structure": raw_source,
            "trb_path": str(trb_path) if trb_path.exists() else "",
            "raw_backbone_motif_rmsd": fmt(rmsd["raw_backbone_motif_rmsd"]),
            "motif_atoms_compared": fmt(rmsd["motif_atoms_compared"]),
            "motif_atoms_missing": fmt(rmsd["motif_atoms_missing"]),
            "motif_residue_count": fmt(len(motif_ref)),
            "motif_residues_mapped": fmt(sum(1 for item in mapped if item is not None)),
            "motif_residue_mapping_status": mapping_status,
            "local_support_residue_count": fmt(local_support_count(atoms, mapped, support_cutoff)),
            "backbone_length": fmt(len(unique_residues(atoms))),
            "raw_backbone_clash_count_around_motif": fmt(local_clash_count(atoms, mapped, clash_neighborhood_cutoff, clash_cutoff)),
            "output_normalization_status": norm_status,
            "normalization_metadata": norm_meta,
        })
    return rows


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", action="append", required=True, help="backend_name=/path/to/run_dir")
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--atom_names", default=",".join(BACKBONE_ATOMS))
    parser.add_argument("--support_cutoff", type=float, default=8.0)
    parser.add_argument("--clash_neighborhood_cutoff", type=float, default=4.0)
    parser.add_argument("--clash_cutoff", type=float, default=2.0)
    args = parser.parse_args()

    atom_names = [item.strip() for item in args.atom_names.split(",") if item.strip()]
    rows = []
    for backend, run_dir in parse_backend_specs(args.backend).items():
        rows.extend(audit_backend(
            backend,
            run_dir,
            Path(args.reference_pdb).resolve(),
            Path(args.motif_tsv).resolve(),
            atom_names,
            args.support_cutoff,
            args.clash_neighborhood_cutoff,
            args.clash_cutoff,
        ))
    write_csv(Path(args.output_csv), rows)
    print("Wrote %d raw backbone motif audit rows to %s" % (len(rows), args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
