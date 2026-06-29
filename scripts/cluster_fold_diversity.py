#!/usr/bin/env python3
"""Cluster filtered designs by global fold, motif-local geometry, and sequence."""

import argparse
import csv
import json
import math
import os
import re
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

import numpy as np

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from pdb_metrics import (  # noqa: E402
    BACKBONE_ATOMS,
    atom_lookup,
    kabsch_rmsd,
    map_motif_residues,
    read_motif_tsv,
    read_pdb_atoms,
)


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}


def to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        val = float(value)
    except ValueError:
        return None
    if math.isnan(val):
        return None
    return val


def to_int(value) -> Optional[int]:
    val = to_float(value)
    return None if val is None else int(val)


def fmt(value) -> str:
    return "" if value is None else "%.6g" % value


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def abs_or_join(path: str, base_dir: Path) -> Path:
    p = Path(path)
    return p if p.is_absolute() else base_dir / p


def find_tool() -> Tuple[str, str]:
    candidates = [
        ("usalign", "USalign"),
        ("us-align", "US-align"),
        ("tmalign", "TMalign"),
        ("tm-align", "TM-align"),
        ("TM-align", "TM-align"),
    ]
    for label, exe in candidates:
        hit = shutil.which(exe)
        if hit:
            return label, hit
    return "python_ca_rmsd_fallback", ""


def parse_tm_score(output: str) -> Optional[float]:
    scores = []
    for line in output.splitlines():
        if "TM-score" not in line:
            continue
        match = re.search(r"TM-score\s*=\s*([0-9.]+)", line)
        if match:
            scores.append(float(match.group(1)))
    if not scores:
        return None
    return max(scores)


def external_tm_score(tool_path: str, pdb_a: Path, pdb_b: Path) -> Optional[float]:
    try:
        proc = subprocess.run(
            [tool_path, str(pdb_a), str(pdb_b)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            timeout=60,
        )
    except Exception:
        return None
    return parse_tm_score(proc.stdout)


def residue_sequence_and_ca(path: Path):
    residues = []
    seen = set()
    ca_coords = []
    for atom in read_pdb_atoms(str(path)):
        key = (atom["chain"], atom["resseq"], atom["icode"])
        if key not in seen:
            seen.add(key)
            residues.append((atom["chain"], atom["resseq"], atom["icode"], AA3_TO_1.get(atom["resname"], "X")))
        if atom["atom"] == "CA":
            ca_coords.append(atom["coord"])
    return residues, np.asarray(ca_coords, dtype=float)


def aligned_rmsd(coords_a, coords_b) -> Optional[float]:
    n = min(len(coords_a), len(coords_b))
    if n < 3:
        return None
    return kabsch_rmsd(np.asarray(coords_a[:n], dtype=float), np.asarray(coords_b[:n], dtype=float))


def rmsd_similarity(rmsd: Optional[float]) -> Optional[float]:
    if rmsd is None:
        return None
    return 1.0 / (1.0 + (rmsd / 5.0) ** 2)


def connected_components(ids: List[str], similar_pairs: Iterable[Tuple[str, str]]) -> Dict[str, int]:
    parent = {item: item for item in ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[rb] = ra

    for a, b in similar_pairs:
        union(a, b)
    roots = {}
    out = {}
    for item in sorted(ids):
        root = find(item)
        if root not in roots:
            roots[root] = len(roots) + 1
        out[item] = roots[root]
    return out


def read_fasta_sequences(paths: List[Path]) -> Dict[str, str]:
    sequences = {}
    for path in paths:
        if not path.exists() or not path.is_file():
            continue
        header = None
        chunks = []
        for raw in path.read_text(errors="ignore").splitlines():
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if header and chunks:
                    sequences[header] = "".join(chunks)
                header = line[1:].split()[0].split(",")[0]
                chunks = []
            else:
                chunks.append(line)
        if header and chunks:
            sequences[header] = "".join(chunks)
    return sequences


def sequence_identity(seq_a: str, seq_b: str) -> Optional[float]:
    if not seq_a or not seq_b:
        return None
    n = min(len(seq_a), len(seq_b))
    if n == 0:
        return None
    matches = sum(1 for a, b in zip(seq_a[:n], seq_b[:n]) if a == b)
    return matches / max(len(seq_a), len(seq_b))


def design_from_long_id(text: str) -> str:
    match = re.match(r"(design_\d+)", text)
    return match.group(1) if match else text


def local_path_from_row_path(raw: str, pdb_dir: Path, design_id: str, summary_dir: Path) -> Optional[Path]:
    candidates = []
    if raw:
        p = Path(raw)
        if p.exists():
            return p
        if not p.is_absolute():
            rel = summary_dir / p
            if rel.exists():
                return rel
            candidates.append(p.name)
        else:
            candidates.append(p.name)
    candidates.extend([design_id + ".pdb"])
    for name in candidates:
        hits = sorted(
            [p for p in pdb_dir.rglob(name) if p.exists() and p.is_file()],
            key=lambda p: (0 if "predictions_flat" in p.parts else 1, len(str(p))),
        )
        if hits:
            return hits[0]
    hits = sorted(
        [p for p in pdb_dir.rglob(design_id + "*.pdb") if p.exists() and p.is_file()],
        key=lambda p: (0 if "predictions_flat" in p.parts else 1, len(str(p))),
    )
    return hits[0] if hits else None


def infer_sequence(row, fasta_sequences, pdb_path: Optional[Path]) -> str:
    json_sequence = row.get("_json_sequence", "")
    if json_sequence:
        return json_sequence
    design_id = row["design_id"]
    for key in [row.get("sequence_key", ""), row.get("long_design_id", ""), design_id]:
        if key and key in fasta_sequences:
            return fasta_sequences[key]
    for key, seq in fasta_sequences.items():
        if key.startswith(design_id) or design_id in key:
            return seq
    if pdb_path and pdb_path.exists():
        residues, _ = residue_sequence_and_ca(pdb_path)
        return "".join(r[3] for r in residues)
    return ""


def sequence_from_json(path: Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return ""
    chains = payload.get("chains")
    if isinstance(chains, list):
        return "".join(str(chain.get("sequence", "")) for chain in chains if chain.get("sequence"))
    sequences = payload.get("sequences")
    if isinstance(sequences, list):
        chunks = []
        for item in sequences:
            protein = item.get("protein") if isinstance(item, dict) else None
            if isinstance(protein, dict) and protein.get("sequence"):
                chunks.append(str(protein["sequence"]))
        return "".join(chunks)
    return ""


def localize_remote_path(path_text: str, anchors: List[Path]) -> Optional[Path]:
    if not path_text:
        return None
    path = Path(path_text)
    if path.exists():
        return path
    name = path.name
    for anchor in anchors:
        if not anchor.exists():
            continue
        hits = sorted([p for p in anchor.rglob(name) if p.exists() and p.is_file()], key=lambda p: len(str(p)))
        if hits:
            return hits[0]
    return None


def sequence_from_prediction_assets(row, summary_dir: Path, pdb_dir: Path) -> str:
    design_id = row["design_id"]
    anchors = [summary_dir.parent, pdb_dir]
    task_dir_text = row.get("task_dir", "")
    task_dir = localize_remote_path(task_dir_text, anchors) if task_dir_text else None
    candidate_jsons = []
    if task_dir:
        manifest = task_dir / "prediction_inputs/af3/manifest.tsv"
        if manifest.exists():
            for manifest_row in read_csv(manifest):
                path = localize_remote_path(manifest_row.get("json_path", ""), [task_dir, summary_dir.parent, pdb_dir])
                if path:
                    candidate_jsons.append(path)
        candidate_jsons.extend(sorted((task_dir / "prediction_inputs/af3").glob("*.json")))
    canonical_dir = summary_dir.parent / "canonical" / design_id / "json"
    if canonical_dir.exists():
        candidate_jsons.extend(sorted(canonical_dir.glob("*.json")))
    for path in candidate_jsons:
        seq = sequence_from_json(path)
        if seq:
            row["sequence_key"] = path.stem
            return seq
    return ""


def pass_threshold(row, args, prefix="") -> bool:
    if row.get(prefix + "pass", row.get("pass")) != "PASS":
        return False
    plddt = to_float(row.get(prefix + "plddt_mean", row.get("plddt_mean")))
    pae = to_float(row.get(prefix + "pae_mean", row.get("pae_mean")))
    motif = to_float(row.get(prefix + "motif_rmsd", row.get("motif_rmsd")))
    clashes = to_int(row.get(prefix + "clash_count", row.get("clash_count")))
    missing = to_int(row.get(prefix + "motif_atoms_missing", row.get("motif_atoms_missing")))
    if plddt is not None and plddt < args.min_plddt:
        return False
    if pae is not None and pae > args.max_pae:
        return False
    if motif is not None and motif > args.max_motif_rmsd:
        return False
    if clashes is not None and clashes > args.max_clashes:
        return False
    if missing is not None and missing > 0:
        return False
    return True


def normalize_summary_rows(args) -> List[Dict[str, str]]:
    summary_path = Path(args.summary_csv)
    rows = read_csv(summary_path)
    if rows and "predictor" in rows[0]:
        grouped = defaultdict(dict)
        for row in rows:
            grouped[row["design_id"]][row["predictor"]] = row
        out = []
        for design_id, by_pred in grouped.items():
            if args.predictor == "consensus":
                af3 = by_pred.get("af3", {})
                rf3 = by_pred.get("rf3", {})
                boltz = by_pred.get("boltz", {})
                if not af3:
                    continue
                row = {
                    "design_id": design_id,
                    "predictor": "consensus",
                    "af3_pass": af3.get("pass", ""),
                    "rf3_pass": rf3.get("pass", ""),
                    "pass": "PASS" if af3.get("pass") == "PASS" and rf3.get("pass") == "PASS" else "FAIL",
                    "plddt_mean": af3.get("plddt_mean", ""),
                    "pae_mean": af3.get("pae_mean", ""),
                    "motif_rmsd": af3.get("motif_rmsd", ""),
                    "clash_count": af3.get("clash_count", ""),
                    "motif_atoms_missing": af3.get("motif_atoms_missing", ""),
                    "model_pdb": af3.get("model_output_path", ""),
                    "confidence_file": af3.get("confidence_file", ""),
                    "rf3_plddt_mean": rf3.get("plddt_mean", ""),
                    "rf3_pae_mean": rf3.get("pae_mean", ""),
                    "rf3_motif_rmsd": rf3.get("motif_rmsd", ""),
                    "rf3_clash_count": rf3.get("clash_count", ""),
                    "rf3_motif_atoms_missing": rf3.get("motif_atoms_missing", ""),
                    "boltz_warning": "",
                }
                if boltz and boltz.get("prediction_status") == "SUCCESS" and boltz.get("pass") != "PASS":
                    reasons = []
                    if to_float(boltz.get("plddt_mean")) is not None and to_float(boltz.get("plddt_mean")) < args.min_plddt:
                        reasons.append("low_plddt")
                    if to_float(boltz.get("motif_rmsd")) is not None and to_float(boltz.get("motif_rmsd")) > args.max_motif_rmsd:
                        reasons.append("high_motif_rmsd")
                    row["boltz_warning"] = "BOLTZ_SINGLE_SEQUENCE_DISAGREEMENT:%s" % (";".join(reasons) or "filter_fail")
                out.append(row)
            else:
                row = by_pred.get(args.predictor)
                if row:
                    out.append({
                        "design_id": design_id,
                        "predictor": args.predictor,
                        "pass": row.get("pass", ""),
                        "plddt_mean": row.get("plddt_mean", ""),
                        "pae_mean": row.get("pae_mean", ""),
                        "motif_rmsd": row.get("motif_rmsd", ""),
                        "clash_count": row.get("clash_count", ""),
                        "motif_atoms_missing": row.get("motif_atoms_missing", ""),
                        "model_pdb": row.get("model_output_path", ""),
                        "confidence_file": row.get("confidence_file", ""),
                        "boltz_warning": "",
                    })
        return out
    out = []
    for row in rows:
        row = dict(row)
        row.setdefault("predictor", args.predictor)
        row.setdefault("model_pdb", row.get("model_output_path", ""))
        row.setdefault("boltz_warning", "")
        out.append(row)
    return out


def score_row(row):
    motif = to_float(row.get("motif_rmsd")) or 999.0
    rf3_motif = to_float(row.get("rf3_motif_rmsd"))
    max_motif = max([v for v in [motif, rf3_motif] if v is not None], default=motif)
    plddt = to_float(row.get("plddt_mean")) or 0.0
    rf3_plddt = to_float(row.get("rf3_plddt_mean"))
    mean_plddt = np.mean([v for v in [plddt, rf3_plddt] if v is not None])
    pae = to_float(row.get("pae_mean")) or 999.0
    rf3_pae = to_float(row.get("rf3_pae_mean"))
    mean_pae = np.mean([v for v in [pae, rf3_pae] if v is not None])
    missing = to_int(row.get("motif_atoms_missing")) or 0
    clashes = to_int(row.get("clash_count")) or 0
    return (0 if row.get("pass") == "PASS" else 1, max_motif, -mean_plddt, mean_pae, missing, clashes, row["design_id"])


def choose_representatives(rows, cluster_key):
    by_cluster = defaultdict(list)
    for row in rows:
        by_cluster[row[cluster_key]].append(row)
    reps = {}
    for cluster_id, items in by_cluster.items():
        rep = sorted(items, key=score_row)[0]
        reps[cluster_id] = rep["design_id"]
    return reps


def select_candidates(rows, top_n):
    selected = []
    counts_global = defaultdict(int)
    used_motif = set()
    used_sequence = set()
    for row in sorted(rows, key=score_row):
        if len(selected) >= top_n:
            break
        if row.get("pass") != "PASS":
            continue
        global_id = row["fold_cluster_id"]
        motif_id = row["motif_local_cluster_id"]
        seq_id = row["sequence_cluster_id"]
        if counts_global[global_id] >= 2:
            continue
        if motif_id in used_motif and len(selected) < max(1, top_n // 2):
            continue
        if seq_id in used_sequence and len(selected) < max(1, top_n // 2):
            continue
        selected.append(row)
        counts_global[global_id] += 1
        used_motif.add(motif_id)
        used_sequence.add(seq_id)
    if len(selected) < top_n:
        for row in sorted(rows, key=score_row):
            if len(selected) >= top_n:
                break
            if row in selected or row.get("pass") != "PASS":
                continue
            if counts_global[row["fold_cluster_id"]] >= 2:
                continue
            selected.append(row)
            counts_global[row["fold_cluster_id"]] += 1
    return selected


def motif_model_residues(reference_pdb, model_pdb, motif_tsv, trb_path=None):
    motif_ref = read_motif_tsv(motif_tsv)
    motif_model = map_motif_residues(motif_ref, str(trb_path) if trb_path else None)
    model_atoms = read_pdb_atoms(str(model_pdb))
    lookup = atom_lookup(model_atoms)
    coords = []
    missing = 0
    for chain, resseq in motif_model:
        for atom_name in BACKBONE_ATOMS:
            key = (chain, resseq, atom_name)
            if key in lookup:
                coords.append(lookup[key])
            else:
                missing += 1
    return np.asarray(coords, dtype=float), missing, motif_model, model_atoms


def local_support_coords(model_atoms, motif_residues, radius=10.0):
    motif_ca = []
    for atom in model_atoms:
        if atom["atom"] == "CA" and (atom["chain"], atom["resseq"]) in set(motif_residues):
            motif_ca.append(atom["coord"])
    if not motif_ca:
        return np.empty((0, 3), dtype=float), 0
    motif_ca = np.asarray(motif_ca, dtype=float)
    support_residues = set()
    for atom in model_atoms:
        if atom["record"] != "ATOM":
            continue
        if atom["atom"] == "CA":
            dmin = np.sqrt(((motif_ca - atom["coord"]) ** 2).sum(axis=1)).min()
            if dmin <= radius:
                support_residues.add((atom["chain"], atom["resseq"]))
    lookup = atom_lookup(model_atoms)
    coords = []
    for chain, resseq in sorted(support_residues):
        for atom_name in BACKBONE_ATOMS:
            coord = lookup.get((chain, resseq, atom_name))
            if coord is not None:
                coords.append(coord)
    return np.asarray(coords, dtype=float), len(support_residues)


def find_trb_for_design(row, pdb_path: Optional[Path], summary_dir: Path):
    design_id = row["design_id"]
    candidates = []
    if pdb_path:
        candidates.append(pdb_path.with_suffix(".trb"))
        candidates.append(pdb_path.parent.parent / (design_id + ".trb"))
    candidates.append(summary_dir.parent / "rfdiffusion_outputs" / (design_id + ".trb"))
    if pdb_path:
        for parent in pdb_path.parents:
            candidates.append(parent / "rfdiffusion_outputs" / (design_id + ".trb"))
    candidates.append(summary_dir / "predictions_flat" / "rf3_mappings" / (pdb_path.stem + ".trb" if pdb_path else design_id + ".trb"))
    for p in candidates:
        if p.exists():
            return p
    return None


def build_records(args):
    summary_path = Path(args.summary_csv)
    summary_dir = summary_path.parent
    pdb_dir = Path(args.pdb_dir)
    fasta_paths = []
    if args.sequence_fasta:
        fp = Path(args.sequence_fasta)
        if fp.is_dir():
            fasta_paths.extend(fp.rglob("*.fa"))
            fasta_paths.extend(fp.rglob("*.fasta"))
        else:
            fasta_paths.append(fp)
    else:
        fasta_paths.extend(pdb_dir.rglob("*.fa"))
        fasta_paths.extend(pdb_dir.rglob("*.fasta"))
        fasta_paths.extend(summary_dir.parent.rglob("*.fa"))
        fasta_paths.extend(summary_dir.parent.rglob("*.fasta"))
    fasta_sequences = read_fasta_sequences(fasta_paths)
    records = []
    for row in normalize_summary_rows(args):
        if not pass_threshold(row, args):
            continue
        pdb_path = local_path_from_row_path(row.get("model_pdb", ""), pdb_dir, row["design_id"], summary_dir)
        if not pdb_path:
            continue
        row = dict(row)
        row["model_pdb"] = str(pdb_path)
        row["_json_sequence"] = sequence_from_prediction_assets(row, summary_dir, pdb_dir)
        row["sequence"] = infer_sequence(row, fasta_sequences, pdb_path)
        row["sequence_length"] = len(row["sequence"])
        row["trb_path"] = str(find_trb_for_design(row, pdb_path, summary_dir) or "")
        _residues, ca = residue_sequence_and_ca(pdb_path)
        row["_ca"] = ca
        motif_coords, motif_missing, motif_residues, model_atoms = motif_model_residues(
            args.reference_pdb, pdb_path, args.motif_tsv, row["trb_path"] or None
        )
        local_coords, support_count = local_support_coords(model_atoms, motif_residues, radius=args.local_radius)
        row["_motif_coords"] = motif_coords
        row["_local_coords"] = local_coords
        row["local_support_residue_count"] = support_count
        row["computed_motif_atoms_missing"] = motif_missing
        records.append(row)
    return records


def cluster_global(records, args, tool_label, tool_path):
    similar = []
    pair_metrics = {}
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            key = (a["design_id"], b["design_id"])
            if tool_path:
                tm = external_tm_score(tool_path, Path(a["model_pdb"]), Path(b["model_pdb"]))
                pair_metrics[key] = {"tm_score": tm, "ca_rmsd": ""}
                if tm is not None and tm >= args.tm_threshold:
                    similar.append(key)
            else:
                rmsd = aligned_rmsd(a["_ca"], b["_ca"])
                sim = rmsd_similarity(rmsd)
                pair_metrics[key] = {"tm_score": sim, "ca_rmsd": rmsd}
                if sim is not None and sim >= args.tm_threshold:
                    similar.append(key)
    clusters = connected_components([r["design_id"] for r in records], similar)
    for row in records:
        row["fold_cluster_id"] = "F%d" % clusters[row["design_id"]]
    reps = choose_representatives(records, "fold_cluster_id")
    sizes = defaultdict(int)
    for row in records:
        sizes[row["fold_cluster_id"]] += 1
    for row in records:
        row["fold_cluster_size"] = sizes[row["fold_cluster_id"]]
        row["fold_representative_design"] = reps[row["fold_cluster_id"]]
        row["fold_representative_reason"] = "best_filter_score_in_cluster"
    return pair_metrics


def cluster_motif_local(records, args):
    similar = []
    pair_metrics = {}
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            rmsd = aligned_rmsd(a["_local_coords"], b["_local_coords"])
            key = (a["design_id"], b["design_id"])
            pair_metrics[key] = rmsd
            if rmsd is not None and rmsd <= args.motif_local_rmsd_threshold:
                similar.append(key)
    clusters = connected_components([r["design_id"] for r in records], similar)
    for row in records:
        row["motif_local_cluster_id"] = "M%d" % clusters[row["design_id"]]
    reps = choose_representatives(records, "motif_local_cluster_id")
    sizes = defaultdict(int)
    for row in records:
        sizes[row["motif_local_cluster_id"]] += 1
    for row in records:
        row["motif_local_cluster_size"] = sizes[row["motif_local_cluster_id"]]
        row["motif_local_representative_design"] = reps[row["motif_local_cluster_id"]]
    return pair_metrics


def cluster_sequence(records, args):
    similar = []
    pair_metrics = {}
    for i, a in enumerate(records):
        for b in records[i + 1:]:
            ident = sequence_identity(a.get("sequence", ""), b.get("sequence", ""))
            key = (a["design_id"], b["design_id"])
            pair_metrics[key] = ident
            if ident is not None and ident >= args.seq_identity_threshold:
                similar.append(key)
    clusters = connected_components([r["design_id"] for r in records], similar)
    for row in records:
        row["sequence_cluster_id"] = "S%d" % clusters[row["design_id"]]
    reps = choose_representatives(records, "sequence_cluster_id")
    sizes = defaultdict(int)
    rep_seq = {}
    for row in records:
        sizes[row["sequence_cluster_id"]] += 1
        if row["design_id"] == reps[row["sequence_cluster_id"]]:
            rep_seq[row["sequence_cluster_id"]] = row.get("sequence", "")
    for row in records:
        row["sequence_cluster_size"] = sizes[row["sequence_cluster_id"]]
        row["sequence_representative_design"] = reps[row["sequence_cluster_id"]]
        row["sequence_identity_to_representative"] = sequence_identity(row.get("sequence", ""), rep_seq.get(row["sequence_cluster_id"], ""))
    return pair_metrics


def write_csv(path, rows, fieldnames):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def make_output_rows(records):
    rows = []
    for row in records:
        rows.append({
            "design_id": row["design_id"],
            "predictor": row.get("predictor", ""),
            "model_pdb": row.get("model_pdb", ""),
            "fold_cluster_id": row["fold_cluster_id"],
            "cluster_size": row["fold_cluster_size"],
            "representative_design": row["fold_representative_design"],
            "representative_reason": row["fold_representative_reason"],
            "motif_local_cluster_id": row["motif_local_cluster_id"],
            "motif_rmsd_to_reference": row.get("motif_rmsd", ""),
            "local_support_residue_count": row.get("local_support_residue_count", ""),
            "motif_atoms_missing": row.get("motif_atoms_missing", row.get("computed_motif_atoms_missing", "")),
            "sequence_cluster_id": row["sequence_cluster_id"],
            "sequence_identity_to_representative": fmt(row.get("sequence_identity_to_representative")),
            "sequence_length": row.get("sequence_length", ""),
            "sequence_representative_design": row["sequence_representative_design"],
            "plddt_mean": row.get("plddt_mean", ""),
            "pae_mean": row.get("pae_mean", ""),
            "clash_count": row.get("clash_count", ""),
            "boltz_warning": row.get("boltz_warning", ""),
            "rf3_plddt_mean": row.get("rf3_plddt_mean", ""),
            "rf3_pae_mean": row.get("rf3_pae_mean", ""),
            "rf3_motif_rmsd": row.get("rf3_motif_rmsd", ""),
        })
    return rows


def write_shortlist(out_dir, records):
    top5 = select_candidates(records, 5)
    top10 = select_candidates(records, 10)
    rows = []
    seen = set()
    rank = 1
    for row in top10:
        status = "top5" if row in top5 else "top10"
        seen.add(row["design_id"])
        strict_motif = (
            (to_float(row.get("motif_rmsd")) or 999.0) < 1.5 and
            (to_float(row.get("rf3_motif_rmsd")) is None or (to_float(row.get("rf3_motif_rmsd")) or 999.0) < 1.5)
        )
        pass_label = "AF3/RF3 PASS" if row.get("rf3_motif_rmsd") else "AF3 PASS"
        rows.append({
            "rank": rank,
            "design_id": row["design_id"],
            "selection_status": status,
            "selection_reason": "%s; diversity-aware representative; %s" % (pass_label, "motif_rmsd_lt_1.5" if strict_motif else "motif_rmsd_threshold_pass"),
            "global_fold_cluster_id": row["fold_cluster_id"],
            "motif_local_cluster_id": row["motif_local_cluster_id"],
            "sequence_cluster_id": row["sequence_cluster_id"],
            "AF3 pLDDT": row.get("plddt_mean", ""),
            "AF3 PAE": row.get("pae_mean", ""),
            "AF3 motif RMSD": row.get("motif_rmsd", ""),
            "RF3 pLDDT": row.get("rf3_plddt_mean", ""),
            "RF3 PAE": row.get("rf3_pae_mean", ""),
            "RF3 motif RMSD": row.get("rf3_motif_rmsd", ""),
            "Boltz warning": row.get("boltz_warning", ""),
            "model_pdb": row.get("model_pdb", ""),
            "recommended_for_expression": "yes" if status == "top5" else "no",
        })
        rank += 1
    for row in sorted(records, key=score_row):
        if row["design_id"] in seen:
            continue
        rows.append({
            "rank": rank,
            "design_id": row["design_id"],
            "selection_status": "not_selected",
            "selection_reason": "lower_rank_or_cluster_redundant",
            "global_fold_cluster_id": row["fold_cluster_id"],
            "motif_local_cluster_id": row["motif_local_cluster_id"],
            "sequence_cluster_id": row["sequence_cluster_id"],
            "AF3 pLDDT": row.get("plddt_mean", ""),
            "AF3 PAE": row.get("pae_mean", ""),
            "AF3 motif RMSD": row.get("motif_rmsd", ""),
            "RF3 pLDDT": row.get("rf3_plddt_mean", ""),
            "RF3 PAE": row.get("rf3_pae_mean", ""),
            "RF3 motif RMSD": row.get("rf3_motif_rmsd", ""),
            "Boltz warning": row.get("boltz_warning", ""),
            "model_pdb": row.get("model_pdb", ""),
            "recommended_for_expression": "no",
        })
        rank += 1
    fields = [
        "rank", "design_id", "selection_status", "selection_reason",
        "global_fold_cluster_id", "motif_local_cluster_id", "sequence_cluster_id",
        "AF3 pLDDT", "AF3 PAE", "AF3 motif RMSD",
        "RF3 pLDDT", "RF3 PAE", "RF3 motif RMSD",
        "Boltz warning", "model_pdb", "recommended_for_expression",
    ]
    write_csv(out_dir / "diverse_shortlist.csv", rows, fields)
    return rows


def write_report(out_dir, records, tool_label, args):
    fold_clusters = len(set(r["fold_cluster_id"] for r in records))
    motif_clusters = len(set(r["motif_local_cluster_id"] for r in records))
    seq_clusters = len(set(r["sequence_cluster_id"] for r in records))
    selected = [r for r in read_csv(out_dir / "diverse_shortlist.csv") if r["selection_status"] in ("top5", "top10")]
    lines = [
        "# Fold Clustering Report",
        "",
        "Input summary: `%s`" % args.summary_csv,
        "Predictor mode: `%s`" % args.predictor,
        "Structure clustering backend: `%s`" % tool_label,
        "",
    ]
    if tool_label == "python_ca_rmsd_fallback":
        lines.append("US-align/TM-align was not found, so global fold clustering used pairwise Kabsch C-alpha RMSD converted to an approximate similarity score. This fallback is useful for small local triage but is less stable than TM-score for topology-level clustering.")
        lines.append("")
    lines.extend([
        "## Cluster Counts",
        "",
        "- Designs retained after thresholds: %d" % len(records),
        "- Global fold clusters: %d" % fold_clusters,
        "- Motif-local clusters: %d" % motif_clusters,
        "- Sequence clusters: %d" % seq_clusters,
        "",
        "## Shortlist",
        "",
        "| rank | design | status | global | motif-local | sequence | recommended |",
        "| ---: | --- | --- | --- | --- | --- | --- |",
    ])
    for row in selected[:10]:
        lines.append("| {rank} | {design_id} | {selection_status} | {global_fold_cluster_id} | {motif_local_cluster_id} | {sequence_cluster_id} | {recommended_for_expression} |".format(**row))
    lines.extend([
        "",
        "Boltz single-sequence disagreement, when present, is reported as a warning and is not used as a hard selection gate.",
        "",
    ])
    (out_dir / "cluster_report.md").write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--summary_csv", required=True)
    parser.add_argument("--pdb_dir", required=True)
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--sequence_fasta", default="")
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--predictor", default="af3", choices=["af3", "rf3", "consensus"])
    parser.add_argument("--min_plddt", type=float, default=70.0)
    parser.add_argument("--max_pae", type=float, default=10.0)
    parser.add_argument("--max_motif_rmsd", type=float, default=2.0)
    parser.add_argument("--max_clashes", type=int, default=20)
    parser.add_argument("--tm_threshold", type=float, default=0.6)
    parser.add_argument("--motif_local_rmsd_threshold", type=float, default=2.0)
    parser.add_argument("--seq_identity_threshold", type=float, default=0.8)
    parser.add_argument("--local_radius", type=float, default=10.0)
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    records = build_records(args)
    if not records:
        raise SystemExit("no designs retained after filtering and PDB resolution")
    tool_label, tool_path = find_tool()
    cluster_global(records, args, tool_label, tool_path)
    cluster_motif_local(records, args)
    cluster_sequence(records, args)
    rows = make_output_rows(records)
    write_csv(out_dir / "fold_cluster_summary.csv", rows, [
        "design_id", "predictor", "model_pdb", "fold_cluster_id", "cluster_size",
        "representative_design", "representative_reason", "plddt_mean", "pae_mean",
        "motif_rmsd_to_reference", "clash_count", "boltz_warning",
    ])
    write_csv(out_dir / "motif_local_cluster_summary.csv", rows, [
        "design_id", "predictor", "motif_local_cluster_id", "motif_rmsd_to_reference",
        "local_support_residue_count", "motif_atoms_missing", "representative_design",
        "model_pdb",
    ])
    for row in rows:
        row["representative_design"] = row["sequence_representative_design"]
    write_csv(out_dir / "sequence_cluster_summary.csv", rows, [
        "design_id", "predictor", "sequence_cluster_id", "sequence_identity_to_representative",
        "sequence_length", "representative_design", "model_pdb",
    ])
    write_shortlist(out_dir, records)
    write_report(out_dir, records, tool_label, args)
    print("Clustered %d designs into %s" % (len(records), out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
