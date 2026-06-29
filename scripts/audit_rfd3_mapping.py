#!/usr/bin/env python3
"""Audit Foundry RFD3 motif mapping through MPNN, AF3, and RF3 layers."""

import argparse
import csv
import json
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))
from pdb_metrics import load_rfdiffusion_trb_mapping, read_motif_tsv, read_pdb_atoms  # noqa: E402


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
    "MSE": "M",
}

FIELDS = [
    "audit_group",
    "design_id",
    "af3_pass",
    "af3_plddt",
    "af3_pae",
    "af3_motif_rmsd",
    "raw_output_structure",
    "normalized_pdb",
    "trb_path",
    "fixed_positions_jsonl",
    "proteinmpnn_fasta",
    "canonical_manifest",
    "af3_input_json",
    "af3_model_pdb",
    "rf3_model_pdb",
    "rf3_pass",
    "motif_reference_sequence",
    "motif_normalized_pdb_sequence",
    "motif_designed_fasta_sequence",
    "motif_af3_input_sequence",
    "motif_af3_model_sequence",
    "motif_rf3_model_sequence",
    "motif_residue_count_expected",
    "motif_residue_count_mapped",
    "motif_residue_order_status",
    "motif_chain_status",
    "fixed_position_status",
    "proteinmpnn_motif_sequence_status",
    "af3_input_motif_sequence_status",
    "af3_model_motif_sequence_status",
    "rf3_model_motif_sequence_status",
    "overall_mapping_status",
    "notes",
]


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def read_tsv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def natural_design_key(text: str) -> Tuple:
    return tuple(int(p) if p.isdigit() else p for p in re.split(r"(\d+)", text))


def select_rows(rows: List[Dict[str, str]], pass_count: int, fail_count: int) -> List[Tuple[str, Dict[str, str]]]:
    pass_rows = [row for row in rows if row.get("pass") == "PASS"]
    fail_rows = [row for row in rows if row.get("pass") != "PASS"]
    pass_rows = sorted(pass_rows, key=lambda r: natural_design_key(r.get("design_id") or r.get("backbone_id", "")))
    fail_rows = sorted(fail_rows, key=lambda r: natural_design_key(r.get("design_id") or r.get("backbone_id", "")))
    return [("PASS", row) for row in pass_rows[:pass_count]] + [("FAIL", row) for row in fail_rows[:fail_count]]


def foundry_output_map(run_dir: Path) -> Dict[str, Dict[str, str]]:
    path = run_dir / "rfdiffusion_outputs" / "foundry_output_map.json"
    if not path.exists():
        return {}
    payload = json.loads(path.read_text())
    if not isinstance(payload, list):
        return {}
    return {item.get("design_id", ""): item for item in payload}


def residues_from_pdb(path: Path) -> List[Dict[str, object]]:
    residues = []
    seen = set()
    for atom in read_pdb_atoms(str(path)):
        if atom["record"] != "ATOM":
            continue
        key = (atom["chain"], atom["resseq"], atom["icode"])
        if key in seen:
            continue
        seen.add(key)
        residues.append({
            "chain": atom["chain"],
            "resseq": atom["resseq"],
            "icode": atom["icode"],
            "aa": AA3_TO_1.get(atom["resname"].upper(), "X"),
        })
    return residues


def sequence_for_residues(path: Path, residues: Sequence[Tuple[str, int]]) -> str:
    by_id = {(r["chain"], r["resseq"]): r["aa"] for r in residues_from_pdb(path)}
    return "".join(by_id.get((chain, resseq), "X") for chain, resseq in residues)


def mapped_residues(motif_ref: Sequence[Tuple[str, int]], trb_path: Path) -> List[Optional[Tuple[str, int]]]:
    if not trb_path.exists():
        return [None for _ in motif_ref]
    mapping = load_rfdiffusion_trb_mapping(str(trb_path))
    if not mapping:
        return list(motif_ref)
    return [mapping.get(item) for item in motif_ref]


def sequence_for_optional_residues(path: Path, residues: Sequence[Optional[Tuple[str, int]]]) -> str:
    by_id = {(r["chain"], r["resseq"]): r["aa"] for r in residues_from_pdb(path)}
    seq = []
    for item in residues:
        if item is None:
            seq.append("X")
        else:
            seq.append(by_id.get(item, "X"))
    return "".join(seq)


def residue_positions(path: Path) -> Dict[Tuple[str, int], int]:
    positions = {}
    counts = {}
    for residue in residues_from_pdb(path):
        chain = residue["chain"]
        counts[chain] = counts.get(chain, 0) + 1
        positions[(chain, residue["resseq"])] = counts[chain]
    return positions


def read_fixed_positions(path: Path, design_id: str) -> Dict[str, List[int]]:
    if not path.exists():
        return {}
    for raw in path.read_text().splitlines():
        if not raw.strip():
            continue
        payload = json.loads(raw)
        if design_id in payload:
            return payload[design_id]
        if payload:
            return next(iter(payload.values()))
    return {}


def read_fasta(path: Path) -> List[Tuple[str, str]]:
    records = []
    if not path.exists():
        return records
    header = None
    chunks: List[str] = []
    for raw in path.read_text(errors="ignore").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith(">"):
            if header and chunks:
                records.append((header, "".join(chunks)))
            header = line[1:].strip()
            chunks = []
        else:
            chunks.append(line)
    if header and chunks:
        records.append((header, "".join(chunks)))
    return records


def first_design_sequence(path: Path) -> str:
    records = read_fasta(path)
    if len(records) >= 2:
        return records[1][1]
    if records:
        return records[0][1]
    return ""


def first_tsv_path(path: Path, column: str) -> str:
    rows = read_tsv(path)
    if rows:
        return rows[0].get(column, "")
    return ""


def sequence_from_af3_json(path: Path) -> str:
    if not path.exists():
        return ""
    try:
        payload = json.loads(path.read_text())
    except Exception:
        return ""
    pieces = []
    for item in payload.get("sequences", []):
        protein = item.get("protein", {}) if isinstance(item, dict) else {}
        if protein.get("sequence"):
            pieces.append(protein["sequence"])
    return "".join(pieces)


def sequence_slice(sequence: str, positions: Sequence[int]) -> str:
    out = []
    for pos in positions:
        idx = pos - 1
        out.append(sequence[idx] if 0 <= idx < len(sequence) else "X")
    return "".join(out)


def status_equal(observed: str, expected: str, empty_label: str = "missing") -> str:
    if not observed:
        return empty_label
    return "ok" if observed == expected else "mismatch"


def chain_status(mapped: Sequence[Optional[Tuple[str, int]]]) -> str:
    chains = sorted({item[0] for item in mapped if item is not None})
    if not chains:
        return "missing"
    return "ok:%s" % ",".join(chains) if len(chains) == 1 else "multi_chain:%s" % ",".join(chains)


def order_status(mapped: Sequence[Optional[Tuple[str, int]]]) -> str:
    present = [item for item in mapped if item is not None]
    if len(present) != len(mapped):
        return "partial"
    chains = {item[0] for item in present}
    if len(chains) != 1:
        return "multi_chain"
    nums = [item[1] for item in present]
    return "ok" if nums == sorted(nums) and len(set(nums)) == len(nums) else "out_of_order_or_duplicate"


def fixed_position_status(fixed: Dict[str, List[int]], chain: str, expected_positions: Sequence[int]) -> str:
    values = fixed.get(chain) or fixed.get("A") or []
    if list(values) == list(expected_positions):
        return "ok"
    missing = sorted(set(expected_positions) - set(values))
    extra = sorted(set(values) - set(expected_positions))
    return "mismatch_missing_%d_extra_%d" % (len(missing), len(extra))


def first_existing(paths: Iterable[Path]) -> Path:
    for path in paths:
        if path and path.exists() and path.is_file():
            return path
    return Path("")


def file_path(text: str) -> Path:
    if not text:
        return Path("")
    path = Path(text)
    return path if path.exists() and path.is_file() else Path("")


def is_file(path: Path) -> bool:
    return bool(str(path)) and path.exists() and path.is_file()


def audit_one(
    audit_group: str,
    row: Dict[str, str],
    run_dir: Path,
    rf3_by_design: Dict[str, Dict[str, str]],
    foundry_map: Dict[str, Dict[str, str]],
    reference_pdb: Path,
    motif_ref: Sequence[Tuple[str, int]],
    reference_sequence: str,
) -> Dict[str, str]:
    design_id = row.get("design_id") or row.get("backbone_id")
    rfdiffusion_dir = run_dir / "rfdiffusion_outputs"
    normalized_pdb = rfdiffusion_dir / ("%s.pdb" % design_id)
    trb_path = rfdiffusion_dir / ("%s.trb" % design_id)
    task_dir = run_dir / "array_work" / design_id
    fixed_path = task_dir / "mpnn_outputs" / "fixed_positions.jsonl"
    fasta_path = task_dir / "mpnn_outputs" / "seqs" / ("%s.fa" % design_id)
    canonical_manifest = task_dir / "prediction_inputs" / "canonical" / "canonical_manifest.tsv"
    af3_manifest = task_dir / "prediction_inputs" / "af3" / "manifest.tsv"
    af3_json = file_path(first_tsv_path(af3_manifest, "json_path"))
    if not is_file(af3_json):
        af3_json = first_existing(sorted((task_dir / "prediction_inputs" / "af3").glob("*.json")))
    af3_model = file_path(row.get("model_pdb", ""))
    rf3_row = rf3_by_design.get(design_id, {})
    rf3_model = file_path(rf3_row.get("model_pdb", ""))

    mapped = mapped_residues(motif_ref, trb_path)
    motif_positions = residue_positions(normalized_pdb) if normalized_pdb.exists() else {}
    expected_positions = [motif_positions[item] for item in mapped if item is not None and item in motif_positions]
    mapped_chain = next((item[0] for item in mapped if item is not None), "A")

    normalized_seq = sequence_for_optional_residues(normalized_pdb, mapped) if normalized_pdb.exists() else ""
    designed_seq = sequence_slice(first_design_sequence(fasta_path), expected_positions)
    af3_input_seq = sequence_slice(sequence_from_af3_json(af3_json), expected_positions)
    af3_model_seq = sequence_for_optional_residues(af3_model, mapped) if is_file(af3_model) else ""
    rf3_model_seq = sequence_for_optional_residues(rf3_model, mapped) if is_file(rf3_model) else ""
    fixed = read_fixed_positions(fixed_path, design_id)

    fixed_status = fixed_position_status(fixed, mapped_chain, expected_positions)
    statuses = {
        "motif_residue_order_status": order_status(mapped),
        "motif_chain_status": chain_status(mapped),
        "fixed_position_status": fixed_status,
        "proteinmpnn_motif_sequence_status": status_equal(designed_seq, reference_sequence),
        "af3_input_motif_sequence_status": status_equal(af3_input_seq, reference_sequence),
        "af3_model_motif_sequence_status": status_equal(af3_model_seq, reference_sequence),
        "rf3_model_motif_sequence_status": status_equal(rf3_model_seq, reference_sequence, empty_label="not_run_or_missing"),
    }
    blocking = [key for key, value in statuses.items() if not (value == "ok" or value.startswith("ok:") or value == "not_run_or_missing")]
    notes = []
    if not is_file(rf3_model):
        notes.append("rf3_model_missing_for_this_design")
    if len(expected_positions) != len(motif_ref):
        notes.append("mapped_positions_%d_of_%d" % (len(expected_positions), len(motif_ref)))

    foundry_item = foundry_map.get(design_id, {})
    out = {
        "audit_group": audit_group,
        "design_id": design_id,
        "af3_pass": row.get("pass", ""),
        "af3_plddt": row.get("plddt_mean", ""),
        "af3_pae": row.get("pae_mean", ""),
        "af3_motif_rmsd": row.get("motif_rmsd", ""),
        "raw_output_structure": foundry_item.get("source_structure", ""),
        "normalized_pdb": str(normalized_pdb) if normalized_pdb.exists() else "",
        "trb_path": str(trb_path) if trb_path.exists() else "",
        "fixed_positions_jsonl": str(fixed_path) if fixed_path.exists() else "",
        "proteinmpnn_fasta": str(fasta_path) if fasta_path.exists() else "",
        "canonical_manifest": str(canonical_manifest) if canonical_manifest.exists() else "",
        "af3_input_json": str(af3_json) if is_file(af3_json) else "",
        "af3_model_pdb": str(af3_model) if is_file(af3_model) else "",
        "rf3_model_pdb": str(rf3_model) if is_file(rf3_model) else "",
        "rf3_pass": rf3_row.get("pass", ""),
        "motif_reference_sequence": reference_sequence,
        "motif_normalized_pdb_sequence": normalized_seq,
        "motif_designed_fasta_sequence": designed_seq,
        "motif_af3_input_sequence": af3_input_seq,
        "motif_af3_model_sequence": af3_model_seq,
        "motif_rf3_model_sequence": rf3_model_seq,
        "motif_residue_count_expected": str(len(motif_ref)),
        "motif_residue_count_mapped": str(sum(1 for item in mapped if item is not None)),
        "overall_mapping_status": "FAIL" if blocking else "PASS",
        "notes": ";".join(notes),
    }
    out.update(statuses)
    return out


def write_csv(path: Path, rows: List[Dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_md(path: Path, rows: List[Dict[str, str]], motif_label: str) -> None:
    ok = sum(1 for row in rows if row["overall_mapping_status"] == "PASS")
    lines = [
        "# RFD3 Mapping Audit",
        "",
        "Motif audited: `%s`." % motif_label,
        "",
        "This audit follows selected Foundry RFD3 Phase 1 designs from raw Foundry output through normalization, TRB mapping, ProteinMPNN fixed positions, canonical predictor inputs, AF3 output, and RF3 confirmation when present.",
        "",
        "## Summary",
        "",
        "- Designs audited: %d" % len(rows),
        "- Mapping PASS: %d" % ok,
        "- Mapping FAIL: %d" % (len(rows) - ok),
        "",
        "| group | design | AF3 pass | mapped residues | fixed positions | MPNN motif | AF3 input | AF3 model | RF3 model | overall |",
        "| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        lines.append(
            "| {audit_group} | {design_id} | {af3_pass} | {motif_residue_count_mapped}/{motif_residue_count_expected} | {fixed_position_status} | {proteinmpnn_motif_sequence_status} | {af3_input_motif_sequence_status} | {af3_model_motif_sequence_status} | {rf3_model_motif_sequence_status} | {overall_mapping_status} |".format(**row)
        )
    lines.extend([
        "",
        "## Interpretation Rule",
        "",
        "- If normalized PDB/TRB/fixed positions/FASTA/AF3 input all preserve the motif but AF3/RF3 motif RMSD degrades, the likely failure layer is downstream scaffold stability or predictor response, not RFD3 motif mapping.",
        "- If any fixed-position or sequence-preservation field is `mismatch`, the RFD3 result is not interpretable until normalization and fixed-position mapping are corrected.",
        "",
    ])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run_dir", required=True, help="Foundry RFD3 Phase 1 run directory.")
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--filter_summary", default="", help="AF3 all_filter_summary.csv. Defaults to run_dir/reports/all_filter_summary.csv.")
    parser.add_argument("--rf3_filter_summary", default="", help="RF3 filter summary, if available.")
    parser.add_argument("--output_csv", required=True)
    parser.add_argument("--output_md", required=True)
    parser.add_argument("--pass_count", type=int, default=3)
    parser.add_argument("--fail_count", type=int, default=3)
    args = parser.parse_args()

    run_dir = Path(args.run_dir).resolve()
    filter_summary = Path(args.filter_summary) if args.filter_summary else run_dir / "reports" / "all_filter_summary.csv"
    rf3_summary = Path(args.rf3_filter_summary) if args.rf3_filter_summary else run_dir / "reports" / "rf3_filter_summary.csv"
    motif_ref = read_motif_tsv(args.motif_tsv)
    reference_sequence = sequence_for_residues(Path(args.reference_pdb), motif_ref)
    rows = read_csv(filter_summary)
    rf3_by_design = {row.get("design_id") or row.get("backbone_id", ""): row for row in read_csv(rf3_summary)}
    foundry_map = foundry_output_map(run_dir)

    audit_rows = [
        audit_one(group, row, run_dir, rf3_by_design, foundry_map, Path(args.reference_pdb), motif_ref, reference_sequence)
        for group, row in select_rows(rows, args.pass_count, args.fail_count)
    ]
    write_csv(Path(args.output_csv), audit_rows)
    write_md(Path(args.output_md), audit_rows, "A163-181")
    print("Wrote %d RFD3 mapping audit rows to %s" % (len(audit_rows), args.output_csv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
