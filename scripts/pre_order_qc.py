#!/usr/bin/env python3
"""Pre-order sequence and structure QC for expression candidates."""

import argparse
import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

from pdb_metrics import (
    BACKBONE_ATOMS,
    atom_lookup,
    count_clashes,
    map_motif_residues,
    read_motif_tsv,
    read_pdb_atoms,
    selected_atom_pairs,
)


MOTIF_SEQUENCE = "EVNKIKSALLSTNKAVVSL"
CANONICAL_AA = set("ACDEFGHIKLMNPQRSTVWY")
HYDROPHOBIC_AA = set("AVILMFWY")
AA_MASS = {
    "A": 89.0935, "R": 174.2017, "N": 132.1184, "D": 133.1032, "C": 121.1590,
    "E": 147.1299, "Q": 146.1451, "G": 75.0669, "H": 155.1552, "I": 131.1736,
    "L": 131.1736, "K": 146.1882, "M": 149.2124, "F": 165.1900, "P": 115.1310,
    "S": 105.0930, "T": 119.1197, "W": 204.2262, "Y": 181.1894, "V": 117.1469,
}
PKA = {
    "nterm": 9.69, "cterm": 2.34, "C": 8.33, "D": 3.86, "E": 4.25,
    "H": 6.00, "K": 10.50, "R": 12.40, "Y": 10.07,
}
VDW = {"H": 1.20, "C": 1.70, "N": 1.55, "O": 1.52, "S": 1.80, "P": 1.80}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: List[Dict[str, object]], fieldnames: List[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def first_existing(paths: Iterable[Path]) -> Optional[Path]:
    for path in paths:
        if path.exists():
            return path
    return None


def find_by_design(root: Path, design_id: str, suffix: str) -> Optional[Path]:
    if not root.exists():
        return None
    hits = sorted([p for p in root.rglob(design_id + "*" + suffix) if p.is_file()])
    if not hits:
        return None
    hits.sort(key=lambda p: (0 if "predictions_flat" in p.parts else 1, len(str(p))))
    return hits[0]


def read_fasta(path: Optional[Path]) -> str:
    if not path or not path.exists():
        return ""
    chunks = []
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if line and not line.startswith(">"):
            chunks.append(line)
    return "".join(chunks)


def sequence_identity(seq_a: str, seq_b: str) -> Optional[float]:
    if not seq_a or not seq_b:
        return None
    n = min(len(seq_a), len(seq_b))
    if n == 0:
        return None
    matches = sum(1 for a, b in zip(seq_a[:n], seq_b[:n]) if a == b)
    return matches / max(len(seq_a), len(seq_b))


def molecular_weight(seq: str) -> Optional[float]:
    if not seq or any(aa not in AA_MASS for aa in seq):
        return None
    return sum(AA_MASS[aa] for aa in seq) - 18.01528 * (len(seq) - 1)


def charge_at_ph(seq: str, ph: float) -> float:
    charge = 1.0 / (1.0 + 10 ** (ph - PKA["nterm"]))
    charge -= 1.0 / (1.0 + 10 ** (PKA["cterm"] - ph))
    counts = {aa: seq.count(aa) for aa in set(seq)}
    for aa in ("K", "R", "H"):
        charge += counts.get(aa, 0) / (1.0 + 10 ** (ph - PKA[aa]))
    for aa in ("D", "E", "C", "Y"):
        charge -= counts.get(aa, 0) / (1.0 + 10 ** (PKA[aa] - ph))
    return charge


def predicted_pi(seq: str) -> Optional[float]:
    if not seq or any(aa not in CANONICAL_AA for aa in seq):
        return None
    low, high = 0.0, 14.0
    for _ in range(60):
        mid = (low + high) / 2.0
        if charge_at_ph(seq, mid) > 0:
            low = mid
        else:
            high = mid
    return (low + high) / 2.0


def glyco_motifs(seq: str) -> List[str]:
    hits = []
    for idx in range(len(seq) - 2):
        triad = seq[idx:idx + 3]
        if triad[0] == "N" and triad[1] != "P" and triad[2] in ("S", "T"):
            hits.append("%s%d-%d" % (triad, idx + 1, idx + 3))
    return hits


def hydrophobic_stretches(seq: str, min_len: int = 7) -> List[str]:
    hits = []
    start = None
    for idx, aa in enumerate(seq + "X"):
        if aa in HYDROPHOBIC_AA:
            if start is None:
                start = idx
        elif start is not None:
            if idx - start >= min_len:
                hits.append("%s%d-%d" % (seq[start:idx], start + 1, idx))
            start = None
    return hits


def low_complexity_regions(seq: str, window: int = 12, max_unique: int = 3) -> List[str]:
    hits = []
    for idx in range(0, max(0, len(seq) - window + 1)):
        chunk = seq[idx:idx + window]
        if len(set(chunk)) <= max_unique:
            hits.append("%s%d-%d" % (chunk, idx + 1, idx + window))
    return hits[:10]


def repetitive_regions(seq: str) -> List[str]:
    hits = []
    for match in re.finditer(r"([A-Z])\1{4,}", seq):
        hits.append("%s%d-%d" % (match.group(0), match.start() + 1, match.end()))
    for size in (2, 3):
        pattern = re.compile(r"(([A-Z]{%d})\2{3,})" % size)
        for match in pattern.finditer(seq):
            hits.append("%s%d-%d" % (match.group(1), match.start(1) + 1, match.end(1)))
    return hits[:10]


def parse_float(value: str) -> Optional[float]:
    try:
        if value in ("", None):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def sequence_qc(design_rows: List[Dict[str, str]], sequences: Dict[str, str]) -> List[Dict[str, object]]:
    rows = []
    best_identity = {}
    for a in design_rows:
        vals = []
        for b in design_rows:
            if a["design_id"] == b["design_id"]:
                continue
            ident = sequence_identity(sequences.get(a["design_id"], ""), sequences.get(b["design_id"], ""))
            if ident is not None:
                vals.append((ident, b["design_id"]))
        best_identity[a["design_id"]] = max(vals, default=(None, ""))

    for row in design_rows:
        design_id = row["design_id"]
        seq = sequences.get(design_id, "")
        motif_start = seq.find(MOTIF_SEQUENCE)
        noncanonical = sorted(set(seq) - CANONICAL_AA)
        hydrophobic = hydrophobic_stretches(seq)
        low_complexity = low_complexity_regions(seq)
        repeats = repetitive_regions(seq)
        glyco = glyco_motifs(seq)
        mw = molecular_weight(seq)
        pi = predicted_pi(seq)
        concerns = []
        if not seq:
            concerns.append("missing_sequence")
        if noncanonical:
            concerns.append("noncanonical_residues")
        if motif_start < 0:
            concerns.append("motif_sequence_missing")
        if hydrophobic:
            concerns.append("long_hydrophobic_stretch")
        if low_complexity or repeats:
            concerns.append("low_complexity_or_repeats")
        if seq.count("C") >= 3:
            concerns.append("multiple_cysteines")
        if len(seq) < 50:
            concerns.append("short_construct")
        if len(seq) > 250:
            concerns.append("long_construct")
        if glyco:
            concerns.append("nxs_t_glycosylation_motif")
        best_ident, best_match = best_identity[design_id]
        if best_ident is not None and best_ident >= 0.9:
            concerns.append("high_sequence_redundancy_with_%s" % best_match)
        rows.append({
            "design_id": design_id,
            "tier": row.get("tier", ""),
            "amino_acid_sequence": seq,
            "sequence_length": len(seq),
            "noncanonical_residues": ";".join(noncanonical),
            "motif_sequence": MOTIF_SEQUENCE,
            "motif_intact": "yes" if motif_start >= 0 else "no",
            "motif_start": motif_start + 1 if motif_start >= 0 else "",
            "motif_end": motif_start + len(MOTIF_SEQUENCE) if motif_start >= 0 else "",
            "cysteine_count": seq.count("C"),
            "nxs_t_glycosylation_motifs": ";".join(glyco),
            "long_hydrophobic_stretches": ";".join(hydrophobic),
            "low_complexity_repetitive_regions": ";".join(low_complexity + repeats),
            "predicted_molecular_weight_da": "%.2f" % mw if mw is not None else "",
            "predicted_pI": "%.2f" % pi if pi is not None else "",
            "max_sequence_identity_to_other_candidate": "" if best_ident is None else "%.4f" % best_ident,
            "most_similar_candidate": best_match,
            "obvious_cloning_gene_synthesis_concerns": ";".join(concerns) if concerns else "none_detected_at_protein_sequence_level",
        })
    return rows


def heavy_atoms(path: Path):
    return [atom for atom in read_pdb_atoms(str(path)) if atom["record"] == "ATOM" and atom["element"] != "H"]


def fibonacci_sphere(n: int = 96) -> np.ndarray:
    points = []
    phi = math.pi * (3.0 - math.sqrt(5.0))
    for idx in range(n):
        y = 1 - (idx / float(n - 1)) * 2
        radius = math.sqrt(max(0.0, 1 - y * y))
        theta = phi * idx
        points.append((math.cos(theta) * radius, y, math.sin(theta) * radius))
    return np.asarray(points, dtype=float)


def motif_sasa_proxy(model_pdb: Path, motif_tsv: Path, trb_path: Optional[Path], sphere_points: int = 96) -> Dict[str, object]:
    atoms = heavy_atoms(model_pdb)
    motif_ref = read_motif_tsv(str(motif_tsv))
    motif_model = set(map_motif_residues(motif_ref, str(trb_path) if trb_path else None))
    motif_atoms = [atom for atom in atoms if (atom["chain"], atom["resseq"]) in motif_model]
    if not motif_atoms:
        return {"motif_sasa_proxy_a2": "", "motif_sasa_accessible_fraction": "", "motif_sasa_note": "motif_atoms_not_found"}
    coords = np.asarray([atom["coord"] for atom in atoms], dtype=float)
    spheres = fibonacci_sphere(sphere_points)
    probe = 1.4
    total_area = 0.0
    accessible_area = 0.0
    for atom in motif_atoms:
        element = str(atom.get("element") or atom["atom"][0]).strip().upper()[:1]
        radius = VDW.get(element, 1.70) + probe
        atom_coord = np.asarray(atom["coord"], dtype=float)
        sample_points = atom_coord + spheres * radius
        atom_area = 4.0 * math.pi * radius * radius
        accessible = 0
        for point in sample_points:
            blocked = False
            for other, other_coord in zip(atoms, coords):
                if other is atom:
                    continue
                other_element = str(other.get("element") or other["atom"][0]).strip().upper()[:1]
                cutoff = VDW.get(other_element, 1.70) + probe
                if np.sum((point - other_coord) ** 2) < cutoff * cutoff:
                    blocked = True
                    break
            if not blocked:
                accessible += 1
        frac = accessible / float(sphere_points)
        total_area += atom_area
        accessible_area += atom_area * frac
    return {
        "motif_sasa_proxy_a2": "%.2f" % accessible_area,
        "motif_sasa_accessible_fraction": "%.3f" % (accessible_area / total_area if total_area else 0.0),
        "motif_sasa_note": "shrake_rupley_proxy_heavy_atoms_probe_1.4A",
    }


def local_support_count(model_pdb: Path, motif_tsv: Path, trb_path: Optional[Path], radius: float = 8.0) -> int:
    atoms = read_pdb_atoms(str(model_pdb))
    motif_model = set(map_motif_residues(read_motif_tsv(str(motif_tsv)), str(trb_path) if trb_path else None))
    motif_ca = [np.asarray(atom["coord"], dtype=float) for atom in atoms if atom["atom"] == "CA" and (atom["chain"], atom["resseq"]) in motif_model]
    if not motif_ca:
        return 0
    motif_ca_arr = np.asarray(motif_ca, dtype=float)
    support = set()
    for atom in atoms:
        if atom["atom"] != "CA" or (atom["chain"], atom["resseq"]) in motif_model:
            continue
        dmin = np.sqrt(((motif_ca_arr - np.asarray(atom["coord"], dtype=float)) ** 2).sum(axis=1)).min()
        if dmin <= radius:
            support.add((atom["chain"], atom["resseq"]))
    return len(support)


def motif_missing_for_model(reference_pdb: Path, model_pdb: Path, motif_tsv: Path, trb_path: Optional[Path]) -> Dict[str, object]:
    try:
        ref_coords, _model_coords, missing = selected_atom_pairs(
            str(reference_pdb), str(model_pdb), str(motif_tsv), atom_names=BACKBONE_ATOMS, model_trb=str(trb_path) if trb_path else None
        )
        return {"motif_atoms_compared": len(ref_coords), "motif_atoms_missing": len(missing)}
    except Exception as exc:
        return {"motif_atoms_compared": "", "motif_atoms_missing": "", "motif_parse_error": repr(exc)}


def structure_qc(design_rows: List[Dict[str, str]], paths: Dict[str, Dict[str, Optional[Path]]], reference_pdb: Path, motif_tsv: Path) -> List[Dict[str, object]]:
    rows = []
    for row in design_rows:
        design_id = row["design_id"]
        p = paths[design_id]
        af3_pdb = p.get("af3_pdb")
        rf3_pdb = p.get("rf3_pdb")
        trb = p.get("trb")
        missing = motif_missing_for_model(reference_pdb, af3_pdb, motif_tsv, trb) if af3_pdb else {}
        support = local_support_count(af3_pdb, motif_tsv, trb, radius=8.0) if af3_pdb else 0
        exposure = motif_sasa_proxy(af3_pdb, motif_tsv, trb) if af3_pdb else {
            "motif_sasa_proxy_a2": "", "motif_sasa_accessible_fraction": "", "motif_sasa_note": "af3_model_missing",
        }
        clash_count = count_clashes(str(af3_pdb), cutoff=2.0) if af3_pdb else ""
        rows.append({
            "design_id": design_id,
            "tier": row.get("tier", ""),
            "AF3 model path": str(af3_pdb or ""),
            "RF3 model path": str(rf3_pdb or ""),
            "AF3 pLDDT": row.get("AF3 pLDDT", ""),
            "RF3 pLDDT": row.get("RF3 pLDDT", ""),
            "AF3 PAE": row.get("AF3 PAE", ""),
            "RF3 PAE": row.get("RF3 PAE", ""),
            "AF3 motif RMSD": row.get("AF3 motif RMSD", ""),
            "RF3 motif RMSD": row.get("RF3 motif RMSD", ""),
            "motif_atoms_compared": missing.get("motif_atoms_compared", ""),
            "motif_atoms_missing": missing.get("motif_atoms_missing", ""),
            "clash_count": clash_count,
            "local_support_residue_count": support,
            "motif_solvent_exposure_proxy_a2": exposure["motif_sasa_proxy_a2"],
            "motif_solvent_exposure_accessible_fraction": exposure["motif_sasa_accessible_fraction"],
            "motif_solvent_exposure_note": exposure["motif_sasa_note"],
            "fold_cluster": row.get("fold_cluster", ""),
            "motif_local_cluster": row.get("motif_local_cluster", ""),
            "Boltz warning": row.get("Boltz warning", ""),
        })
    return rows


def qc_decisions(sequence_rows: List[Dict[str, object]], structure_rows: List[Dict[str, object]], final_rows: List[Dict[str, str]]) -> List[Dict[str, object]]:
    seq_by = {row["design_id"]: row for row in sequence_rows}
    struct_by = {row["design_id"]: row for row in structure_rows}
    out = []
    for row in final_rows:
        design_id = row["design_id"]
        seq = seq_by[design_id]
        struct = struct_by[design_id]
        risks = []
        severe = []
        caution = []
        if seq["motif_intact"] != "yes":
            severe.append("motif_sequence_missing")
        if seq["noncanonical_residues"]:
            severe.append("noncanonical_residues")
        if seq["long_hydrophobic_stretches"]:
            caution.append("long_hydrophobic_stretch")
        if seq["low_complexity_repetitive_regions"]:
            caution.append("low_complexity_or_repeats")
        if seq["nxs_t_glycosylation_motifs"]:
            caution.append("nxs_t_glycosylation_motif")
        if int(seq["cysteine_count"]) >= 3:
            caution.append("multiple_cysteines")
        if parse_float(row.get("AF3 motif RMSD", "")) is None or parse_float(row.get("RF3 motif RMSD", "")) is None:
            severe.append("missing_consensus_motif_rmsd")
        if parse_float(row.get("AF3 motif RMSD", "")) is not None and parse_float(row.get("AF3 motif RMSD", "")) > 2.0:
            severe.append("af3_motif_rmsd_gt_2")
        if parse_float(row.get("RF3 motif RMSD", "")) is not None and parse_float(row.get("RF3 motif RMSD", "")) > 2.0:
            severe.append("rf3_motif_rmsd_gt_2")
        if row.get("AF3 pass") != "PASS" or row.get("RF3 pass") != "PASS":
            severe.append("af3_or_rf3_not_pass")
        if str(struct.get("motif_atoms_missing", "")) not in ("0", "0.0"):
            severe.append("motif_atoms_missing")
        if parse_float(str(struct.get("clash_count", ""))) is not None and parse_float(str(struct.get("clash_count", ""))) > 20:
            severe.append("excessive_clashes")
        if parse_float(str(struct.get("motif_solvent_exposure_accessible_fraction", ""))) is not None and parse_float(str(struct.get("motif_solvent_exposure_accessible_fraction", ""))) < 0.20:
            caution.append("low_motif_exposure_proxy")
        if row.get("Boltz warning"):
            caution.append("boltz_no_msa_warning")
        risks = severe + caution
        if severe:
            status = "hold"
            order_now = "no"
        elif caution:
            status = "caution"
            order_now = "yes"
        else:
            status = "pass"
            order_now = "yes"
        if row.get("tier") == "backup" and status == "pass":
            status = "caution"
            caution.append("backup_priority")
            risks = severe + caution
        out.append({
            "design_id": design_id,
            "QC_status": status,
            "main_risks": ";".join(risks) if risks else "none",
            "recommended_expression_priority": row.get("expression_priority", ""),
            "recommended_expression_system_placeholder": "TBD_by_user",
            "order_now": order_now,
            "reason": decision_reason(row, status, risks),
        })
    return out


def decision_reason(row: Dict[str, str], status: str, risks: List[str]) -> str:
    if status == "hold":
        return "Hold before cloning because %s." % ";".join(risks)
    if status == "caution":
        return "AF3/RF3 consensus acceptable; review caution flags before ordering: %s." % (";".join(risks) if risks else "backup_priority")
    return "AF3/RF3 consensus strong, motif intact, and no severe sequence flags detected."


def cloning_ready(final_rows: List[Dict[str, str]], decisions: List[Dict[str, object]], sequences: Dict[str, str]) -> List[Dict[str, object]]:
    decision_by = {row["design_id"]: row for row in decisions}
    rows = []
    for row in final_rows:
        decision = decision_by[row["design_id"]]
        if decision["order_now"] != "yes":
            continue
        rows.append({
            "design_id": row["design_id"],
            "tier": row.get("tier", ""),
            "expression_priority": row.get("expression_priority", ""),
            "amino_acid_sequence": sequences.get(row["design_id"], ""),
            "sequence_length": len(sequences.get(row["design_id"], "")),
            "expression_system_placeholder": "TBD_by_user",
            "vector_placeholder": "TBD_by_user",
            "tag_placeholder": "TBD_by_user_no_tag_added",
            "signal_peptide_placeholder": "TBD_by_user_no_signal_peptide_added",
            "linker_placeholder": "TBD_by_user_no_linker_added",
            "restriction_sites_placeholder": "TBD_by_user_no_sites_added",
            "codon_optimization_placeholder": "TBD_by_user_not_applied",
            "QC_status": decision["QC_status"],
            "QC_risks": decision["main_risks"],
            "notes": "Placeholder construct only; no tag, signal peptide, linker, restriction sites, or codon optimization added.",
        })
    return rows


def load_design_paths(final_dir: Path, backup_dir: Path, backend_root: Path, design_id: str) -> Dict[str, Optional[Path]]:
    design_dir = final_dir / design_id
    if design_dir.exists():
        return {
            "sequence_fasta": design_dir / (design_id + "_final_sequence.fasta"),
            "af3_pdb": design_dir / (design_id + "_af3_model.pdb"),
            "rf3_pdb": design_dir / (design_id + "_rf3_model.pdb"),
            "trb": design_dir / (design_id + "_rfdiffusion_mapping.trb"),
        }
    return {
        "sequence_fasta": find_by_design(backup_dir / "canonical" / design_id / "fasta", design_id, ".fasta"),
        "af3_pdb": backend_root / "array_work" / design_id / "predictions_flat" / (design_id + ".pdb"),
        "rf3_pdb": find_by_design(backup_dir / "predictions_flat" / "rf3", design_id, ".pdb"),
        "trb": find_by_design(backup_dir / "predictions_flat" / "rf3_mappings", design_id, ".trb"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--final_dir", required=True)
    parser.add_argument("--backup_dir", required=True)
    parser.add_argument("--backend_root", required=True)
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--out_dir", default="")
    args = parser.parse_args()

    final_dir = Path(args.final_dir)
    backup_dir = Path(args.backup_dir)
    backend_root = Path(args.backend_root)
    out_dir = Path(args.out_dir) if args.out_dir else final_dir / "reports"
    final_rows = read_csv(final_dir / "reports" / "final_expression_shortlist.csv")
    paths = {row["design_id"]: load_design_paths(final_dir, backup_dir, backend_root, row["design_id"]) for row in final_rows}
    sequences = {design_id: read_fasta(p["sequence_fasta"]) for design_id, p in paths.items()}

    seq_rows = sequence_qc(final_rows, sequences)
    struct_rows = structure_qc(final_rows, paths, Path(args.reference_pdb), Path(args.motif_tsv))
    decision_rows = qc_decisions(seq_rows, struct_rows, final_rows)
    cloning_rows = cloning_ready(final_rows, decision_rows, sequences)

    write_csv(out_dir / "pre_order_sequence_qc.csv", seq_rows, [
        "design_id", "tier", "amino_acid_sequence", "sequence_length", "noncanonical_residues",
        "motif_sequence", "motif_intact", "motif_start", "motif_end", "cysteine_count",
        "nxs_t_glycosylation_motifs", "long_hydrophobic_stretches",
        "low_complexity_repetitive_regions", "predicted_molecular_weight_da",
        "predicted_pI", "max_sequence_identity_to_other_candidate", "most_similar_candidate",
        "obvious_cloning_gene_synthesis_concerns",
    ])
    write_csv(out_dir / "pre_order_structure_qc.csv", struct_rows, [
        "design_id", "tier", "AF3 model path", "RF3 model path", "AF3 pLDDT", "RF3 pLDDT",
        "AF3 PAE", "RF3 PAE", "AF3 motif RMSD", "RF3 motif RMSD",
        "motif_atoms_compared", "motif_atoms_missing", "clash_count",
        "local_support_residue_count", "motif_solvent_exposure_proxy_a2",
        "motif_solvent_exposure_accessible_fraction", "motif_solvent_exposure_note",
        "fold_cluster", "motif_local_cluster", "Boltz warning",
    ])
    write_csv(out_dir / "pre_order_qc_decision.csv", decision_rows, [
        "design_id", "QC_status", "main_risks", "recommended_expression_priority",
        "recommended_expression_system_placeholder", "order_now", "reason",
    ])
    write_csv(out_dir / "cloning_ready_constructs.csv", cloning_rows, [
        "design_id", "tier", "expression_priority", "amino_acid_sequence", "sequence_length",
        "expression_system_placeholder", "vector_placeholder", "tag_placeholder",
        "signal_peptide_placeholder", "linker_placeholder", "restriction_sites_placeholder",
        "codon_optimization_placeholder", "QC_status", "QC_risks", "notes",
    ])
    print("Wrote pre-order QC package to %s" % out_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
