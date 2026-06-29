#!/usr/bin/env python3
"""Contact-face QC for epitope-scaffold candidates."""

import argparse
import csv
import math
from pathlib import Path
from statistics import median
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from pdb_metrics import (
    kabsch_rmsd,
    load_rfdiffusion_trb_mapping,
    read_motif_tsv,
    read_pdb_atoms,
    squared_distance,
)


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}

CHARGE_CLASS = {
    "R": "positive", "K": "positive", "H": "positive",
    "D": "negative", "E": "negative",
    "S": "polar", "T": "polar", "N": "polar", "Q": "polar", "Y": "polar", "C": "polar",
    "A": "hydrophobic", "V": "hydrophobic", "L": "hydrophobic", "I": "hydrophobic",
    "M": "hydrophobic", "F": "hydrophobic", "W": "hydrophobic", "P": "hydrophobic",
    "G": "neutral",
}

FIELDS = [
    "condition_id",
    "predictor",
    "design_id",
    "source_pass",
    "model_pdb",
    "contact_residue_count",
    "contact_residues_present",
    "contact_residue_identity_preserved",
    "contact_residue_charge_class_preserved",
    "contact_face_atoms_reference",
    "contact_face_atoms_compared",
    "contact_face_atoms_missing",
    "contact_face_RMSD",
    "whole_motif_exposure_proxy",
    "contact_face_exposure_proxy",
    "local_support_residue_count_8A",
    "local_occluding_atom_count",
    "local_clash_count",
    "decision",
    "caution_flags",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def heavy_atoms(atoms: Iterable[Dict[str, object]]) -> List[Dict[str, object]]:
    return [atom for atom in atoms if atom["record"] == "ATOM" and atom["element"] != "H" and atom["atom"] != "H"]


def residue_letters(atoms: Sequence[Dict[str, object]]) -> Dict[Tuple[str, int], str]:
    out = {}
    for atom in atoms:
        key = (atom["chain"], atom["resseq"])
        if key not in out:
            out[key] = AA3_TO_1.get(str(atom["resname"]).upper(), "X")
    return out


def atom_by_key(atoms: Sequence[Dict[str, object]]) -> Dict[Tuple[str, int, str], Dict[str, object]]:
    return {(atom["chain"], atom["resseq"], atom["atom"]): atom for atom in atoms if atom["record"] == "ATOM"}


def mapped_residue(ref_residue: Tuple[str, int], mapping: Dict[Tuple[str, int], Tuple[str, int]]) -> Tuple[str, int]:
    return mapping.get(ref_residue, ref_residue)


def find_trb(condition_dir: Path, design_id: str) -> Optional[Path]:
    candidates = [
        condition_dir / "rfdiffusion_outputs" / ("%s.trb" % design_id),
        condition_dir / "array_work" / design_id / "trb" / ("%s.trb" % design_id),
    ]
    for path in candidates:
        if path.exists():
            return path
    matches = list(condition_dir.rglob("%s.trb" % design_id))
    return matches[0] if matches else None


def reference_contact_atoms(
    reference_atoms: Sequence[Dict[str, object]],
    contact_residues: Sequence[Tuple[str, int]],
    antibody_chains: Sequence[str],
    cutoff: float,
) -> List[Tuple[str, int, str]]:
    motif_set = set(contact_residues)
    motif_atoms = [atom for atom in heavy_atoms(reference_atoms) if (atom["chain"], atom["resseq"]) in motif_set]
    ab_atoms = [atom for atom in heavy_atoms(reference_atoms) if atom["chain"] in antibody_chains]
    cutoff2 = cutoff * cutoff
    face = []
    for atom in motif_atoms:
        if any(squared_distance(atom["coord"], ab["coord"]) <= cutoff2 for ab in ab_atoms):
            face.append((atom["chain"], atom["resseq"], atom["atom"]))
    return face


def neighbor_count(atoms: Sequence[Dict[str, object]], target: Dict[str, object], motif_set: set, cutoff: float) -> int:
    cutoff2 = cutoff * cutoff
    count = 0
    for atom in atoms:
        residue = (atom["chain"], atom["resseq"])
        if residue in motif_set:
            continue
        if squared_distance(target["coord"], atom["coord"]) <= cutoff2:
            count += 1
    return count


def local_support_count(atoms: Sequence[Dict[str, object]], motif_set: set, cutoff: float) -> int:
    motif_atoms = [atom for atom in atoms if (atom["chain"], atom["resseq"]) in motif_set]
    support = set()
    cutoff2 = cutoff * cutoff
    for atom in atoms:
        residue = (atom["chain"], atom["resseq"])
        if residue in motif_set:
            continue
        if any(squared_distance(atom["coord"], motif_atom["coord"]) <= cutoff2 for motif_atom in motif_atoms):
            support.add(residue)
    return len(support)


def local_clash_count(atoms: Sequence[Dict[str, object]], motif_set: set, shell_cutoff: float, clash_cutoff: float) -> int:
    motif_atoms = [atom for atom in atoms if (atom["chain"], atom["resseq"]) in motif_set]
    shell2 = shell_cutoff * shell_cutoff
    local_atoms = []
    for atom in atoms:
        residue = (atom["chain"], atom["resseq"])
        if residue in motif_set or any(squared_distance(atom["coord"], motif_atom["coord"]) <= shell2 for motif_atom in motif_atoms):
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


def fmt(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float):
        if math.isnan(value):
            return ""
        return "%.6g" % value
    return str(value)


def qc_model(
    condition_id: str,
    predictor: str,
    row: Dict[str, str],
    condition_dir: Path,
    reference_lookup: Dict[Tuple[str, int, str], Dict[str, object]],
    reference_letters: Dict[Tuple[str, int], str],
    contact_residues: Sequence[Tuple[str, int]],
    face_atoms: Sequence[Tuple[str, int, str]],
    neighbor_cutoff: float,
    occlusion_cutoff: float,
    clash_shell_cutoff: float,
    clash_cutoff: float,
) -> Dict[str, str]:
    design_id = row.get("backbone_id") or row.get("design_id", "")
    model_pdb_text = row.get("model_pdb", "")
    model_pdb = Path(model_pdb_text) if model_pdb_text else Path("__missing_model_pdb__")
    flags = []
    if not model_pdb.is_file():
        return {
            "condition_id": condition_id,
            "predictor": predictor,
            "design_id": design_id,
            "source_pass": row.get("pass", ""),
            "model_pdb": str(model_pdb),
            "decision": "contact_face_hold",
            "caution_flags": "model_pdb_missing",
        }

    trb = find_trb(condition_dir, design_id)
    mapping = load_rfdiffusion_trb_mapping(str(trb)) if trb and trb.exists() else {}
    model_atoms = heavy_atoms(read_pdb_atoms(str(model_pdb)))
    model_lookup = atom_by_key(model_atoms)
    model_letters = residue_letters(model_atoms)
    mapped_contact = [mapped_residue(residue, mapping) for residue in contact_residues]
    motif_set = set(mapped_contact)

    present = 0
    identity_ok = 0
    charge_ok = 0
    for ref_residue, model_residue in zip(contact_residues, mapped_contact):
        if model_residue in model_letters:
            present += 1
        ref_letter = reference_letters.get(ref_residue, "X")
        model_letter = model_letters.get(model_residue, "X")
        if model_letter == ref_letter:
            identity_ok += 1
        if CHARGE_CLASS.get(model_letter, "unknown") == CHARGE_CLASS.get(ref_letter, "unknown"):
            charge_ok += 1

    ref_coords = []
    model_coords = []
    missing_atoms = 0
    face_model_atoms = []
    for ref_chain, ref_resseq, atom_name in face_atoms:
        ref_key = (ref_chain, ref_resseq, atom_name)
        model_chain, model_resseq = mapped_residue((ref_chain, ref_resseq), mapping)
        model_key = (model_chain, model_resseq, atom_name)
        if ref_key in reference_lookup and model_key in model_lookup:
            ref_coords.append(reference_lookup[ref_key]["coord"])
            model_coords.append(model_lookup[model_key]["coord"])
            face_model_atoms.append(model_lookup[model_key])
        else:
            missing_atoms += 1

    rmsd = kabsch_rmsd(ref_coords, model_coords) if len(ref_coords) >= 3 else None
    whole_neighbors = [neighbor_count(model_atoms, atom, motif_set, neighbor_cutoff) for atom in model_atoms if (atom["chain"], atom["resseq"]) in motif_set]
    face_neighbors = [neighbor_count(model_atoms, atom, motif_set, neighbor_cutoff) for atom in face_model_atoms]
    whole_exposure = 1.0 / (1.0 + (sum(whole_neighbors) / len(whole_neighbors))) if whole_neighbors else None
    face_exposure = 1.0 / (1.0 + (sum(face_neighbors) / len(face_neighbors))) if face_neighbors else None
    occluding = sum(1 for atom in face_model_atoms if neighbor_count(model_atoms, atom, motif_set, occlusion_cutoff) > 0)
    support = local_support_count(model_atoms, motif_set, neighbor_cutoff)
    clashes = local_clash_count(model_atoms, motif_set, clash_shell_cutoff, clash_cutoff)

    if present < len(contact_residues):
        flags.append("contact_residue_missing")
    if missing_atoms:
        flags.append("contact_face_atoms_missing")
    if rmsd is None or rmsd > 2.5:
        flags.append("contact_face_rmsd_high")
    if face_exposure is not None and face_exposure < 0.08:
        flags.append("contact_face_low_exposure_proxy")
    if occluding > max(3, len(face_model_atoms) // 4):
        flags.append("possible_contact_face_occlusion")
    if clashes > 20:
        flags.append("local_clash_count_high")

    if any(flag in flags for flag in ("contact_residue_missing", "contact_face_atoms_missing")):
        decision = "contact_face_hold"
    elif flags:
        decision = "contact_face_caution"
    else:
        decision = "contact_face_pass"

    return {
        "condition_id": condition_id,
        "predictor": predictor,
        "design_id": design_id,
        "source_pass": row.get("pass", ""),
        "model_pdb": str(model_pdb),
        "contact_residue_count": str(len(contact_residues)),
        "contact_residues_present": str(present),
        "contact_residue_identity_preserved": str(identity_ok),
        "contact_residue_charge_class_preserved": str(charge_ok),
        "contact_face_atoms_reference": str(len(face_atoms)),
        "contact_face_atoms_compared": str(len(ref_coords)),
        "contact_face_atoms_missing": str(missing_atoms),
        "contact_face_RMSD": fmt(rmsd),
        "whole_motif_exposure_proxy": fmt(whole_exposure),
        "contact_face_exposure_proxy": fmt(face_exposure),
        "local_support_residue_count_8A": str(support),
        "local_occluding_atom_count": str(occluding),
        "local_clash_count": str(clashes),
        "decision": decision,
        "caution_flags": ";".join(flags),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    counts: Dict[str, int] = {}
    rmsd_vals = []
    for row in rows:
        counts[row.get("decision", "")] = counts.get(row.get("decision", ""), 0) + 1
        try:
            rmsd_vals.append(float(row.get("contact_face_RMSD", "")))
        except ValueError:
            pass
    lines = [
        "# Contact-Face QC Summary",
        "",
        "- rows: `%d`" % len(rows),
        "- contact_face_pass: `%d`" % counts.get("contact_face_pass", 0),
        "- contact_face_caution: `%d`" % counts.get("contact_face_caution", 0),
        "- contact_face_hold: `%d`" % counts.get("contact_face_hold", 0),
        "- median_contact_face_RMSD: `%s`" % (fmt(median(rmsd_vals)) if rmsd_vals else ""),
        "",
        "Whole-motif RMSD is not a substitute for contact-face QC. This report uses a neighbor-count exposure proxy and should be interpreted as a caution layer.",
    ]
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--condition_id", required=True)
    parser.add_argument("--condition_dir", required=True)
    parser.add_argument("--reference_complex", required=True)
    parser.add_argument("--contact_residue_tsv", required=True)
    parser.add_argument("--antigen_chain", default="A")
    parser.add_argument("--antibody_chains", default="H,L")
    parser.add_argument("--af3_summary", default="")
    parser.add_argument("--rf3_summary", default="")
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--output_md", required=True)
    parser.add_argument("--reference_contact_cutoff", type=float, default=4.0)
    parser.add_argument("--neighbor_cutoff", type=float, default=8.0)
    parser.add_argument("--occlusion_cutoff", type=float, default=4.0)
    parser.add_argument("--clash_shell_cutoff", type=float, default=8.0)
    parser.add_argument("--clash_cutoff", type=float, default=2.0)
    args = parser.parse_args()

    reference_atoms = read_pdb_atoms(args.reference_complex)
    reference_lookup = atom_by_key(reference_atoms)
    reference_letters = residue_letters(reference_atoms)
    contact_residues = read_motif_tsv(args.contact_residue_tsv)
    antibody_chains = [item.strip() for item in args.antibody_chains.split(",") if item.strip()]
    face_atoms = reference_contact_atoms(reference_atoms, contact_residues, antibody_chains, args.reference_contact_cutoff)
    condition_dir = Path(args.condition_dir)

    rows = []
    for predictor, summary_path in [("af3", args.af3_summary), ("rf3", args.rf3_summary)]:
        if not summary_path:
            continue
        for row in read_csv(Path(summary_path)):
            rows.append(qc_model(
                args.condition_id,
                predictor,
                row,
                condition_dir,
                reference_lookup,
                reference_letters,
                contact_residues,
                face_atoms,
                args.neighbor_cutoff,
                args.occlusion_cutoff,
                args.clash_shell_cutoff,
                args.clash_cutoff,
            ))
    write_csv(Path(args.output_csv), rows)
    write_summary(Path(args.output_md), rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
