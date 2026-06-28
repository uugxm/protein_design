#!/usr/bin/env python3
"""PDB geometry metrics for the epitope-scaffold design loop.

The functions here are intentionally dependency-light. They use NumPy for the
Kabsch fit, parse standard ATOM records directly, and understand RFdiffusion
``.trb`` motif mappings when NumPy can load them.
"""

import argparse
import json
import math
import os
import pickle
from collections import OrderedDict

try:
    import numpy as np
except ImportError:
    np = None


BACKBONE_ATOMS = ("N", "CA", "C", "O")


def require_numpy(feature):
    if np is None:
        raise RuntimeError("%s requires NumPy; load the PyTorch/NumPy module or run in the ProteinMPNN environment" % feature)


def make_coord(x, y, z):
    if np is not None:
        return np.array([x, y, z], dtype=float)
    return (float(x), float(y), float(z))


def squared_distance(a, b):
    if np is not None:
        return float(((a - b) ** 2).sum())
    return sum((a[i] - b[i]) ** 2 for i in range(3))


def read_motif_tsv(path):
    """Read motif rows with either chain/start/end or chain/residue columns."""
    rows = []
    with open(path, "r") as handle:
        header = None
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else line.split()
            lower = [p.lower() for p in parts]
            if "chain" in lower and ("start" in lower or "residue" in lower or "position" in lower):
                header = lower
                continue
            if header:
                data = dict(zip(header, parts))
                chain = data.get("chain") or data.get("chain_id")
                if data.get("residue"):
                    rows.append((chain, int(data["residue"]), int(data["residue"])))
                elif data.get("position"):
                    rows.append((chain, int(data["position"]), int(data["position"])))
                else:
                    rows.append((chain, int(data["start"]), int(data["end"])))
            else:
                if len(parts) < 2:
                    continue
                chain = parts[0]
                if len(parts) >= 3 and parts[2].lstrip("-").isdigit():
                    rows.append((chain, int(parts[1]), int(parts[2])))
                else:
                    rows.append((chain, int(parts[1]), int(parts[1])))
    residues = []
    for chain, start, end in rows:
        if start <= end:
            rng = range(start, end + 1)
        else:
            rng = range(start, end - 1, -1)
        for resseq in rng:
            residues.append((chain, resseq))
    return residues


def read_pdb_atoms(path):
    atoms = []
    with open(path, "r", errors="ignore") as handle:
        for line in handle:
            rec = line[:6].strip()
            if rec not in ("ATOM", "HETATM"):
                continue
            atom_name = line[12:16].strip()
            resname = line[17:20].strip()
            chain = line[21:22].strip() or "_"
            try:
                resseq = int(line[22:26])
                x = float(line[30:38])
                y = float(line[38:46])
                z = float(line[46:54])
            except ValueError:
                continue
            icode = line[26:27].strip()
            element = line[76:78].strip() or atom_name[0]
            try:
                bfactor = float(line[60:66])
            except ValueError:
                bfactor = None
            atoms.append({
                "record": rec,
                "atom": atom_name,
                "resname": resname,
                "chain": chain,
                "resseq": resseq,
                "icode": icode,
                "coord": make_coord(x, y, z),
                "element": element.upper(),
                "bfactor": bfactor,
            })
    return atoms


def residue_position_map(atoms):
    """Return mapping from PDB residue IDs to 1-based chain positions."""
    seen = OrderedDict()
    for atom in atoms:
        key = (atom["chain"], atom["resseq"], atom["icode"])
        if key not in seen:
            seen[key] = None
    counts = {}
    mapping = {}
    for chain, resseq, icode in seen:
        counts[chain] = counts.get(chain, 0) + 1
        mapping[(chain, resseq, icode)] = counts[chain]
        mapping[(chain, resseq, "")] = counts[chain]
        mapping[(chain, resseq)] = counts[chain]
    return mapping


def _as_pair(value):
    if isinstance(value, np.ndarray):
        value = value.tolist()
    if isinstance(value, (list, tuple)) and len(value) >= 2:
        return str(value[0]), int(value[1])
    text = str(value)
    chain = text[0]
    digits = "".join(ch for ch in text[1:] if ch.isdigit() or ch == "-")
    if not digits:
        raise ValueError("cannot parse residue pair from %r" % (value,))
    return chain, int(digits)


def load_rfdiffusion_trb_mapping(path):
    """Map original reference residues to hallucinated/output residues."""
    if not path or not os.path.exists(path):
        return {}
    require_numpy("RFdiffusion .trb mapping")
    try:
        payload = np.load(path, allow_pickle=True)
    except Exception:
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
    if "con_ref_pdb_idx" not in payload or "con_hal_pdb_idx" not in payload:
        return {}
    ref = payload["con_ref_pdb_idx"]
    hal = payload["con_hal_pdb_idx"]
    mapping = {}
    for ref_item, hal_item in zip(ref, hal):
        try:
            mapping[_as_pair(ref_item)] = _as_pair(hal_item)
        except Exception:
            continue
    return mapping


def map_motif_residues(motif_residues, trb_path=None):
    if not trb_path:
        return motif_residues
    mapping = load_rfdiffusion_trb_mapping(trb_path)
    if not mapping:
        return motif_residues
    out = []
    for residue in motif_residues:
        if residue in mapping:
            out.append(mapping[residue])
    return out


def atom_lookup(atoms):
    lookup = {}
    for atom in atoms:
        key = (atom["chain"], atom["resseq"], atom["atom"])
        lookup[key] = atom["coord"]
    return lookup


def selected_atom_pairs(reference_pdb, model_pdb, motif_tsv, atom_names=None, model_trb=None):
    if atom_names is None:
        atom_names = BACKBONE_ATOMS
    motif_ref = read_motif_tsv(motif_tsv)
    motif_model = map_motif_residues(motif_ref, model_trb)
    ref_atoms = atom_lookup(read_pdb_atoms(reference_pdb))
    model_atoms = atom_lookup(read_pdb_atoms(model_pdb))
    ref_coords = []
    model_coords = []
    missing = []
    for ref_res, model_res in zip(motif_ref, motif_model):
        ref_chain, ref_resseq = ref_res
        model_chain, model_resseq = model_res
        for atom_name in atom_names:
            ref_key = (ref_chain, ref_resseq, atom_name)
            model_key = (model_chain, model_resseq, atom_name)
            if ref_key in ref_atoms and model_key in model_atoms:
                ref_coords.append(ref_atoms[ref_key])
                model_coords.append(model_atoms[model_key])
            else:
                missing.append({"reference": ref_key, "model": model_key})
    require_numpy("motif RMSD")
    return np.array(ref_coords, dtype=float), np.array(model_coords, dtype=float), missing


def kabsch_rmsd(reference_coords, model_coords):
    if len(reference_coords) < 3 or len(model_coords) < 3:
        return None
    require_numpy("motif RMSD")
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
    aligned = np.dot(mob0, rot)
    diff = aligned - ref0
    return float(np.sqrt((diff * diff).sum() / len(ref)))


def motif_rmsd(reference_pdb, model_pdb, motif_tsv, atom_names=None, model_trb=None):
    ref_coords, model_coords, missing = selected_atom_pairs(
        reference_pdb, model_pdb, motif_tsv, atom_names=atom_names, model_trb=model_trb
    )
    return {
        "motif_rmsd": kabsch_rmsd(ref_coords, model_coords),
        "motif_atoms_compared": int(len(ref_coords)),
        "motif_atoms_missing": int(len(missing)),
    }


def mean_bfactor_plddt(pdb_path):
    values = []
    for atom in read_pdb_atoms(pdb_path):
        if atom["bfactor"] is not None and atom["record"] == "ATOM":
            values.append(atom["bfactor"])
    if not values:
        return None
    return float(sum(values) / len(values))


def count_clashes(pdb_path, cutoff=2.0):
    atoms = [
        atom for atom in read_pdb_atoms(pdb_path)
        if atom["element"] != "H" and atom["atom"] != "H"
    ]
    cutoff2 = cutoff * cutoff
    clashes = 0
    for i, a in enumerate(atoms):
        for b in atoms[i + 1:]:
            if a["chain"] == b["chain"]:
                delta_res = abs(a["resseq"] - b["resseq"])
                if delta_res <= 1:
                    continue
            dist2 = squared_distance(a["coord"], b["coord"])
            if dist2 < cutoff2:
                clashes += 1
    return clashes


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--model_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--model_trb", default="")
    parser.add_argument("--atom_names", default="N,CA,C,O")
    parser.add_argument("--clash_cutoff", type=float, default=2.0)
    args = parser.parse_args()

    atom_names = [item.strip() for item in args.atom_names.split(",") if item.strip()]
    result = motif_rmsd(
        args.reference_pdb,
        args.model_pdb,
        args.motif_tsv,
        atom_names=atom_names,
        model_trb=args.model_trb or None,
    )
    result["clash_count"] = count_clashes(args.model_pdb, cutoff=args.clash_cutoff)
    result["plddt_mean_from_pdb_bfactor"] = mean_bfactor_plddt(args.model_pdb)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
