#!/usr/bin/env python3
"""Validate Foundry RFD3 motif inputs before submitting GPU jobs."""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple

from pdb_metrics import read_motif_tsv, read_pdb_atoms


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}

FIELDS = [
    "condition_id",
    "motif_definition",
    "continuous_or_discontinuous",
    "motif_tsv",
    "input_pdb",
    "input_pdb_exists",
    "motif_residue_count",
    "motif_sequence",
    "motif_segments",
    "fixed_atom_level",
    "selected_atoms_count",
    "all_atom_selection_status",
    "contig",
    "unindex",
    "length",
    "select_fixed_atoms",
    "select_unfixed_sequence",
    "rfd3_input_json",
    "foundry_input_syntax_status",
    "downstream_mapping_status",
    "input_validation_status",
    "gpu_run_allowed",
    "failure_reason",
]


def read_manifest(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def residue_table(pdb_path: Path) -> Dict[Tuple[str, int], Dict[str, object]]:
    table: Dict[Tuple[str, int], Dict[str, object]] = {}
    for atom in read_pdb_atoms(str(pdb_path)):
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"])
        entry = table.setdefault(key, {"resname": atom["resname"], "atoms": []})
        entry["atoms"].append(atom)
    return table


def collapse_ranges(residues: Sequence[Tuple[str, int]]) -> List[Tuple[str, int, int]]:
    if not residues:
        return []
    ranges = []
    start_chain, start_res = residues[0]
    prev_chain, prev_res = residues[0]
    for chain, resseq in residues[1:]:
        if chain == prev_chain and resseq == prev_res + 1:
            prev_res = resseq
            continue
        ranges.append((start_chain, start_res, prev_res))
        start_chain, start_res = chain, resseq
        prev_chain, prev_res = chain, resseq
    ranges.append((start_chain, start_res, prev_res))
    return ranges


def range_text(chain: str, start: int, end: int) -> str:
    return "%s%d" % (chain, start) if start == end else "%s%d-%d" % (chain, start, end)


def selection_text(residues: Sequence[Tuple[str, int]]) -> str:
    return ",".join(range_text(*item) for item in collapse_ranges(residues))


def atom_names_for_mode(mode: str) -> List[str]:
    upper = (mode or "").upper()
    if upper == "BKBN":
        return ["N", "CA", "C", "O"]
    if upper == "TIP":
        return ["CB"]
    if upper == "ALL":
        return []
    return [item.strip() for item in mode.split(",") if item.strip()]


def selected_atom_count(table: Dict[Tuple[str, int], Dict[str, object]], residues: Sequence[Tuple[str, int]], mode: str) -> int:
    names = set(atom_names_for_mode(mode))
    count = 0
    for residue in residues:
        for atom in table.get(residue, {}).get("atoms", []):
            if atom["element"] == "H" or atom["atom"] == "H":
                continue
            if not names or atom["atom"] in names:
                count += 1
    return count


def motif_sequence(table: Dict[Tuple[str, int], Dict[str, object]], residues: Sequence[Tuple[str, int]]) -> str:
    letters = []
    for residue in residues:
        resname = str(table.get(residue, {}).get("resname", "UNK"))
        letters.append(AA3_TO_1.get(resname.upper(), "X"))
    return "".join(letters)


def is_continuous(residues: Sequence[Tuple[str, int]]) -> bool:
    if not residues:
        return False
    return len(collapse_ranges(residues)) == 1


def fixed_atoms_payload(motif_text: str, residues: Sequence[Tuple[str, int]], mode: str, unindex: bool) -> Dict[str, str]:
    if not unindex:
        return {motif_text: mode}
    return {range_text(*item): mode for item in collapse_ranges(residues)}


def condition_json(row: Dict[str, str], reference_pdb: Path, motif_text: str, residues: Sequence[Tuple[str, int]]) -> Dict[str, object]:
    condition_id = row["condition_id"]
    fixed_atoms = row.get("fixed_atoms", "ALL")
    mode = row.get("rfd3_mode", "indexed")
    spec = {
        "dialect": int(row.get("dialect") or 2),
        "input": str(reference_pdb.resolve()),
        "select_fixed_atoms": fixed_atoms_payload(motif_text, residues, fixed_atoms, mode == "unindex"),
        "extra": {
            "condition_id": condition_id,
            "motif_definition": row.get("motif_definition", ""),
            "continuous_or_discontinuous": "continuous" if is_continuous(residues) else "discontinuous",
            "fixed_atom_level": row.get("fixed_atom_level", ""),
            "length_bin": row.get("length_bin", ""),
            "motif_selection": motif_text,
            "motif_source": str(Path(row["motif_tsv"]).resolve()),
            "pilot": "rfd3_contact_motif",
        },
    }
    if mode == "unindex":
        spec["unindex"] = motif_text
        if row.get("length"):
            spec["length"] = row["length"]
    else:
        nterm = row.get("nterm_range") or "20-30"
        cterm = row.get("cterm_range") or "20-30"
        spec["contig"] = ",".join([nterm, motif_text, cterm])
    if row.get("select_unfixed_sequence"):
        spec["select_unfixed_sequence"] = row["select_unfixed_sequence"]
    if row.get("is_non_loopy", "true").lower() in ("1", "true", "yes"):
        spec["is_non_loopy"] = True
    if row.get("partial_t"):
        spec["partial_t"] = float(row["partial_t"])
    return {condition_id: spec}


def write_json(path: Path, payload: Dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def validate_condition(row: Dict[str, str], root: Path, allow_unindex_downstream: bool) -> Dict[str, str]:
    condition_id = row["condition_id"]
    input_pdb = Path(row["input_pdb"])
    motif_tsv = Path(row["motif_tsv"])
    if not input_pdb.is_absolute():
        input_pdb = root / input_pdb
    if not motif_tsv.is_absolute():
        motif_tsv = root / motif_tsv
    row = dict(row)
    row["input_pdb"] = str(input_pdb)
    row["motif_tsv"] = str(motif_tsv)
    condition_dir = root / "conditions" / condition_id
    rfd3_input_json = condition_dir / "rfd3_input.json"
    reasons = []
    foundry_syntax_status = "pass"
    downstream_mapping_status = "pass"

    input_exists = input_pdb.exists()
    if not input_exists:
        reasons.append("input_pdb_missing")
        table = {}
    else:
        table = residue_table(input_pdb)

    if not motif_tsv.exists():
        residues: List[Tuple[str, int]] = []
        reasons.append("motif_tsv_missing")
    else:
        residues = read_motif_tsv(str(motif_tsv))

    missing_residues = [("%s%d" % item) for item in residues if item not in table]
    if missing_residues:
        reasons.append("motif_residues_missing:" + ",".join(missing_residues[:20]))

    fixed_atoms = row.get("fixed_atoms", "ALL")
    atom_count = selected_atom_count(table, residues, fixed_atoms) if table else 0
    if atom_count <= 0:
        reasons.append("selected_atoms_count_zero")
    all_atom_status = "pass" if atom_count > 0 else "fail"

    motif_text = selection_text(residues)
    segments = [range_text(*item) for item in collapse_ranges(residues)]
    mode = row.get("rfd3_mode", "indexed")
    contig = ""
    unindex = ""
    length = row.get("length", "")
    select_unfixed = row.get("select_unfixed_sequence", "")
    if mode == "unindex":
        unindex = motif_text
        if not length:
            reasons.append("unindex_requires_length_for_design_wrapper")
            foundry_syntax_status = "fail"
    else:
        contig = ",".join([row.get("nterm_range") or "20-30", motif_text, row.get("cterm_range") or "20-30"])

    if mode == "indexed" and not is_continuous(residues):
        reasons.append("indexed_contig_discontinuous_motif_not_clean")
        foundry_syntax_status = "fail"
    if mode == "unindex" and contig:
        reasons.append("overlap_between_indexed_and_unindexed_selection")
        foundry_syntax_status = "fail"

    if mode == "unindex" and len(segments) > 1 and not allow_unindex_downstream:
        downstream_mapping_status = "hold_not_cleanly_supported_in_current_wrapper"
        reasons.append(
            "current_normalize_foundry_rfd3_outputs_requires_exact_concatenated_motif_sequence_for_trb_mapping"
        )

    if input_exists and residues:
        payload = condition_json(row, input_pdb, motif_text, residues)
        write_json(rfd3_input_json, payload)
        condition_payload = dict(row)
        condition_payload.update({
            "condition_id": condition_id,
            "motif_residue_count": len(residues),
            "motif_sequence": motif_sequence(table, residues),
            "motif_segments": ",".join(segments),
            "continuous_or_discontinuous": "continuous" if is_continuous(residues) else "discontinuous",
            "contig": contig,
            "unindex": unindex,
            "select_fixed_atoms": json.dumps(payload[condition_id]["select_fixed_atoms"], sort_keys=True),
            "rfd3_input_json": str(rfd3_input_json),
            "phase2_production_started": False,
        })
        write_json(condition_dir / "condition.json", condition_payload)

    status = "valid_ready_to_run"
    gpu_allowed = "yes"
    if reasons:
        if downstream_mapping_status.startswith("hold"):
            status = "hold_not_cleanly_supported_in_current_wrapper"
        else:
            status = "fail"
        gpu_allowed = "no"

    return {
        "condition_id": condition_id,
        "motif_definition": row.get("motif_definition", ""),
        "continuous_or_discontinuous": "continuous" if is_continuous(residues) else "discontinuous",
        "motif_tsv": str(motif_tsv),
        "input_pdb": str(input_pdb),
        "input_pdb_exists": "yes" if input_exists else "no",
        "motif_residue_count": str(len(residues)),
        "motif_sequence": motif_sequence(table, residues) if table else "",
        "motif_segments": ",".join(segments),
        "fixed_atom_level": row.get("fixed_atom_level", ""),
        "selected_atoms_count": str(atom_count),
        "all_atom_selection_status": all_atom_status,
        "contig": contig,
        "unindex": unindex,
        "length": length,
        "select_fixed_atoms": json.dumps(fixed_atoms_payload(motif_text, residues, fixed_atoms, mode == "unindex"), sort_keys=True),
        "select_unfixed_sequence": select_unfixed,
        "rfd3_input_json": str(rfd3_input_json),
        "foundry_input_syntax_status": foundry_syntax_status,
        "downstream_mapping_status": downstream_mapping_status,
        "input_validation_status": status,
        "gpu_run_allowed": gpu_allowed,
        "failure_reason": ";".join(reasons),
    }


def write_csv(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, rows: Sequence[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = ["# RFD3 Contact Motif Input Validation", ""]
    lines.append("| condition | status | gpu | motif | segments | selected atoms | reason |")
    lines.append("| --- | --- | --- | --- | --- | ---: | --- |")
    for row in rows:
        lines.append(
            "| {condition_id} | {input_validation_status} | {gpu_run_allowed} | {motif_definition} | {motif_segments} | {selected_atoms_count} | {failure_reason} |".format(**row)
        )
    lines.extend([
        "",
        "Validation separates Foundry input syntax from current downstream wrapper support.",
        "A condition may be expressible by Foundry but held if normalized PDB/TRB/fixed-position mapping cannot be audited cleanly.",
    ])
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--pilot_root", required=True)
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--output_md", required=True)
    parser.add_argument("--allow_unindex_downstream", action="store_true")
    args = parser.parse_args()

    root = Path(args.pilot_root).resolve()
    rows = [validate_condition(row, root, args.allow_unindex_downstream) for row in read_manifest(Path(args.manifest))]
    write_csv(Path(args.output_csv), rows)
    write_md(Path(args.output_md), rows)
    failures = [row for row in rows if row["input_validation_status"] == "fail"]
    if failures:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
