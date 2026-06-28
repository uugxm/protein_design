#!/usr/bin/env python3
"""Create predictor-neutral inputs from ProteinMPNN FASTA records.

The canonical layer is intentionally small and stable. It records sequences,
chain metadata, reference motif provenance, and an optional backbone structure
copy without adopting any predictor's private JSON schema as the shared format.
"""

import argparse
import csv
import json
import os
import re
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M",
}


def sanitize_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:120] or "design"


def parse_mpnn_score(header: str) -> Optional[float]:
    match = re.search(r"(?:^|[, ])score=([-+]?(?:nan|[0-9]*\.?[0-9]+))", header, re.IGNORECASE)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def read_fasta(path: Path) -> Iterable[Tuple[str, str]]:
    name = None
    chunks: List[str] = []
    with path.open("r") as handle:
        for raw in handle:
            line = raw.strip()
            if not line:
                continue
            if line.startswith(">"):
                if name and chunks:
                    yield name, "".join(chunks)
                name = line[1:].strip()
                chunks = []
            else:
                chunks.append(line)
        if name and chunks:
            yield name, "".join(chunks)


def parse_chain_metadata(path: Optional[Path]) -> Dict[str, Dict[str, str]]:
    if not path:
        return {}
    metadata: Dict[str, Dict[str, str]] = {}
    with path.open("r", newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        for row in reader:
            chain_id = row.get("chain_id") or row.get("chain") or row.get("id")
            if chain_id:
                metadata[chain_id] = row
    return metadata


def read_motif_tsv(path: Optional[Path]) -> List[Dict[str, str]]:
    if not path:
        return []
    rows = []
    with path.open("r") as handle:
        header = None
        for raw in handle:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            parts = line.split("\t") if "\t" in line else line.split()
            lower = [item.lower() for item in parts]
            if "chain" in lower and ("start" in lower or "residue" in lower or "position" in lower):
                header = lower
                continue
            if header:
                rows.append(dict(zip(header, parts)))
            elif len(parts) >= 3:
                rows.append({"chain": parts[0], "start": parts[1], "end": parts[2]})
            elif len(parts) >= 2:
                rows.append({"chain": parts[0], "residue": parts[1]})
    return rows


def pdb_atoms(path: Path) -> Iterable[Dict[str, object]]:
    with path.open("r", errors="ignore") as handle:
        for line in handle:
            record = line[:6].strip()
            if record not in ("ATOM", "HETATM"):
                continue
            try:
                yield {
                    "record": record,
                    "serial": int(line[6:11]),
                    "atom": line[12:16].strip() or "X",
                    "alt": line[16:17].strip() or ".",
                    "resname": line[17:20].strip() or "UNK",
                    "chain": line[21:22].strip() or "A",
                    "resseq": int(line[22:26]),
                    "icode": line[26:27].strip() or ".",
                    "x": float(line[30:38]),
                    "y": float(line[38:46]),
                    "z": float(line[46:54]),
                    "occ": float(line[54:60] or 1.0),
                    "bfac": float(line[60:66] or 0.0),
                    "element": (line[76:78].strip() or line[12:16].strip()[:1] or "X").upper(),
                }
            except ValueError:
                continue


def write_minimal_cif(pdb_path: Path, out_path: Path, data_name: str) -> int:
    atoms = list(pdb_atoms(pdb_path))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w") as handle:
        handle.write("data_%s\n#\n" % sanitize_name(data_name))
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
            handle.write(
                "%s %d %s %s %s %s %s %d %s %.3f %.3f %.3f %.2f %.2f %d %s %s %s\n"
                % (
                    atom["record"], idx, atom["element"], atom["atom"], atom["alt"],
                    atom["resname"], atom["chain"], atom["resseq"], atom["icode"],
                    atom["x"], atom["y"], atom["z"], atom["occ"], atom["bfac"],
                    atom["resseq"], atom["chain"], atom["atom"], atom["resname"],
                )
            )
        handle.write("#\n")
    return len(atoms)


def write_fasta(path: Path, name: str, sequence: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        handle.write(">%s\n" % name)
        for idx in range(0, len(sequence), 80):
            handle.write(sequence[idx:idx + 80] + "\n")


def choose_records(args: argparse.Namespace) -> List[Tuple[str, str, Optional[float]]]:
    records = []
    for idx, (name, sequence) in enumerate(read_fasta(Path(args.fasta))):
        if args.skip_first and idx == 0:
            continue
        records.append((name, sequence, parse_mpnn_score(name)))
    if args.sort_by_score:
        records.sort(key=lambda row: (row[2] is None, row[2] if row[2] is not None else 999999.0, row[0]))
    if args.max_records:
        records = records[:args.max_records]
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fasta", required=True, help="ProteinMPNN FASTA file.")
    parser.add_argument("--out_dir", required=True, help="Canonical prediction input directory.")
    parser.add_argument("--design_id", required=True)
    parser.add_argument("--chain_id", default="A")
    parser.add_argument("--chain_metadata", default="", help="Optional TSV with chain-level overrides.")
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--backbone_pdb", default="", help="Optional generated backbone PDB to preserve as canonical CIF.")
    parser.add_argument("--skip_first", action="store_true")
    parser.add_argument("--max_records", type=int, default=0)
    parser.add_argument("--sort_by_score", action="store_true")
    parser.add_argument("--name_prefix", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    fasta_dir = out_dir / "fasta"
    json_dir = out_dir / "json"
    cif_dir = out_dir / "cif"
    out_dir.mkdir(parents=True, exist_ok=True)

    chain_overrides = parse_chain_metadata(Path(args.chain_metadata) if args.chain_metadata else None)
    motif_rows = read_motif_tsv(Path(args.motif_tsv))
    records = choose_records(args)
    if not records:
        raise SystemExit("no ProteinMPNN FASTA records selected")

    manifest_rows = []
    chain_rows = []
    structure_source = Path(args.backbone_pdb) if args.backbone_pdb else None
    structure_exists = bool(structure_source and structure_source.exists())

    for ordinal, (source_name, sequence, score) in enumerate(records, start=1):
        prefix = args.name_prefix + "_" if args.name_prefix else ""
        job_name = sanitize_name(prefix + source_name)
        if len(records) > 1 and not job_name.startswith(sanitize_name(args.design_id)):
            job_name = sanitize_name("%s_%d_%s" % (args.design_id, ordinal, job_name))

        canonical_fasta = fasta_dir / (job_name + ".fasta")
        canonical_json = json_dir / (job_name + ".json")
        canonical_cif = cif_dir / (job_name + ".cif")
        write_fasta(canonical_fasta, job_name, sequence)

        chain_meta = dict(chain_overrides.get(args.chain_id, {}))
        chain_meta.update({
            "chain_id": args.chain_id,
            "molecule_type": chain_meta.get("molecule_type", "protein"),
            "role": chain_meta.get("role", "designed_scaffold"),
            "sequence": sequence,
            "sequence_length": str(len(sequence)),
            "source_fasta_header": source_name,
            "mpnn_score": "" if score is None else str(score),
        })

        cif_atom_count = 0
        if structure_exists:
            cif_atom_count = write_minimal_cif(structure_source, canonical_cif, job_name)

        payload = {
            "schema": "protein_design.canonical_prediction_input.v1",
            "job_name": job_name,
            "design_id": args.design_id,
            "source_fasta": os.path.abspath(args.fasta),
            "source_fasta_header": source_name,
            "mpnn_score": score,
            "reference_pdb": os.path.abspath(args.reference_pdb),
            "motif_tsv": os.path.abspath(args.motif_tsv),
            "motif_rows": motif_rows,
            "backbone_pdb": os.path.abspath(args.backbone_pdb) if args.backbone_pdb else "",
            "canonical_fasta": str(canonical_fasta.resolve()),
            "canonical_cif": str(canonical_cif.resolve()) if cif_atom_count else "",
            "chains": [chain_meta],
        }
        canonical_json.parent.mkdir(parents=True, exist_ok=True)
        canonical_json.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")

        manifest_rows.append({
            "job_name": job_name,
            "design_id": args.design_id,
            "source_fasta_header": source_name,
            "mpnn_score": "" if score is None else str(score),
            "chain_id": args.chain_id,
            "sequence_length": str(len(sequence)),
            "canonical_fasta": str(canonical_fasta.resolve()),
            "canonical_json": str(canonical_json.resolve()),
            "canonical_cif": str(canonical_cif.resolve()) if cif_atom_count else "",
        })
        chain_rows.append({"job_name": job_name, **chain_meta})

    manifest_path = out_dir / "canonical_manifest.tsv"
    with manifest_path.open("w", newline="") as handle:
        fieldnames = [
            "job_name", "design_id", "source_fasta_header", "mpnn_score", "chain_id",
            "sequence_length", "canonical_fasta", "canonical_json", "canonical_cif",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(manifest_rows)

    chain_path = out_dir / "chain_metadata.tsv"
    chain_fields = []
    for row in chain_rows:
        for key in row:
            if key not in chain_fields:
                chain_fields.append(key)
    with chain_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=chain_fields, delimiter="\t", extrasaction="ignore")
        writer.writeheader()
        writer.writerows(chain_rows)

    print("Wrote %d canonical prediction inputs to %s" % (len(manifest_rows), out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
