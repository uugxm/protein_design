#!/usr/bin/env python3
"""Plan or run the modular epitope-scaffold workflow."""

import argparse
import csv
import json
import shlex
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


SCRIPT_DIR = Path(__file__).resolve().parent
STAGE_ORDER = [
    "input_prep", "motif_extraction", "motif_review", "backbone_generation",
    "sequence_design", "prediction_filtering", "contact_face_qc",
    "fold_clustering", "phage_display_qc", "pre_order_qc", "final_packaging",
]


def script(name: str) -> str:
    return str(SCRIPT_DIR / name)


def add_command(commands: List[Dict[str, object]], stage: str, argv: List[str], outputs: List[str], note: str = "") -> None:
    commands.append({"stage": stage, "argv": argv, "outputs": outputs, "note": note})


def build_commands(args: argparse.Namespace) -> List[Dict[str, object]]:
    py = args.python
    out = Path(args.work_dir)
    commands: List[Dict[str, object]] = []

    if args.complex_pdb and args.motif_ranges:
        add_command(commands, "motif_extraction", [
            py, script("prepare_epitope_from_complex.py"), "--complex_pdb", args.complex_pdb,
            "--motif_ranges", args.motif_ranges, "--out_dir", str(out / "inputs/motif"),
            "--name", args.motif_name, "--copy_reference",
        ], [str(out / "inputs/motif/motif_residues.tsv"), str(out / "inputs/motif/motif_definition.json")])

    add_command(commands, "motif_review", [
        py, script("validate_motif_definition.py"), "--reference_pdb", args.reference_pdb,
        "--motif_tsv", args.motif_tsv, "--out_json", str(out / "reports/motif_validation.json"),
        "--normalized_tsv", str(out / "inputs/motif_residues.normalized.tsv"),
    ], [str(out / "reports/motif_validation.json"), str(out / "inputs/motif_residues.normalized.tsv")])

    if args.rfd3_json:
        add_command(commands, "backbone_generation", [
            py, script("validate_rfd3_motif_input.py"), "--rfd3_json", args.rfd3_json,
            "--out_json", str(out / "reports/rfd3_input_validation.json"),
        ], [str(out / "reports/rfd3_input_validation.json")], "Validates an already prepared Foundry RFD3 input JSON.")

    if args.prediction_json_dir or args.prediction_pdb_dir:
        add_command(commands, "prediction_filtering", [
            py, script("filter_designs.py"), "--input_dir", args.prediction_json_dir or args.prediction_pdb_dir,
            "--pdb_dir", args.prediction_pdb_dir or args.prediction_json_dir, "--reference_pdb", args.reference_pdb,
            "--motif_tsv", args.motif_tsv, "--output_csv", str(out / "reports/filter_summary.csv"),
            "--min_plddt", str(args.min_plddt), "--max_pae", str(args.max_pae),
            "--max_motif_rmsd", str(args.max_motif_rmsd), "--max_clashes", str(args.max_clashes),
        ], [str(out / "reports/filter_summary.csv")])

    if args.prediction_pdb_dir:
        add_command(commands, "contact_face_qc", [
            py, script("contact_face_qc.py"), "--pdb_dir", args.prediction_pdb_dir,
            "--motif_tsv", args.motif_tsv, "--output_csv", str(out / "reports/contact_face_qc.csv"),
        ], [str(out / "reports/contact_face_qc.csv")])

    if args.filter_summary_csv and args.prediction_pdb_dir:
        add_command(commands, "fold_clustering", [
            py, script("cluster_fold_diversity.py"), "--summary_csv", args.filter_summary_csv,
            "--pdb_dir", args.prediction_pdb_dir, "--reference_pdb", args.reference_pdb,
            "--motif_tsv", args.motif_tsv, "--out_dir", str(out / "reports/fold_diversity"),
        ], [str(out / "reports/fold_diversity")])

    if args.sequence_fasta:
        add_command(commands, "phage_display_qc", [
            py, script("phage_display_qc.py"), "--fasta", args.sequence_fasta,
            "--output_csv", str(out / "reports/phage_display_qc.csv"),
        ], [str(out / "reports/phage_display_qc.csv")])

    if args.final_dir and args.backup_dir and args.backend_root:
        add_command(commands, "pre_order_qc", [
            py, script("pre_order_qc.py"), "--final_dir", args.final_dir, "--backup_dir", args.backup_dir,
            "--backend_root", args.backend_root, "--reference_pdb", args.reference_pdb, "--motif_tsv", args.motif_tsv,
            "--out_dir", str(out / "reports/pre_order_qc"),
        ], [str(out / "reports/pre_order_qc")])

    if args.shortlist_csv and args.consensus_csv and args.top_consensus_csv and args.backend_root and args.cross_model_root:
        add_command(commands, "final_packaging", [
            py, script("package_final_candidates.py"), "--shortlist_csv", args.shortlist_csv,
            "--consensus_csv", args.consensus_csv, "--top_consensus_csv", args.top_consensus_csv,
            "--backend_root", args.backend_root, "--cross_model_root", args.cross_model_root,
            "--reference_pdb", args.reference_pdb, "--motif_tsv", args.motif_tsv,
            "--out_dir", args.package_out_dir or str(out / "final_candidates"),
            "--candidate_ids", args.candidate_ids, "--source_backend", args.source_backend,
        ], [args.package_out_dir or str(out / "final_candidates")])

    return [cmd for cmd in commands if args.stage == "all" or cmd["stage"] == args.stage]


def write_manifest(args: argparse.Namespace, commands: List[Dict[str, object]]) -> None:
    out = Path(args.work_dir)
    (out / "reports").mkdir(parents=True, exist_ok=True)
    manifest = {
        "schema": "protein_design.epitope_scaffold_workflow.v1",
        "stage_order": STAGE_ORDER,
        "selected_stage": args.stage,
        "reference_pdb": str(Path(args.reference_pdb).resolve()),
        "motif_tsv": str(Path(args.motif_tsv).resolve()),
        "commands": commands,
    }
    (out / "workflow_manifest.json").write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with (out / "workflow_commands.tsv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stage", "command", "outputs", "note"], delimiter="\t")
        writer.writeheader()
        for cmd in commands:
            writer.writerow({
                "stage": cmd["stage"],
                "command": " ".join(shlex.quote(part) for part in cmd["argv"]),
                "outputs": ";".join(cmd["outputs"]),
                "note": cmd["note"],
            })


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--work_dir", required=True, help="Workflow working directory for manifests and reports.")
    parser.add_argument("--reference_pdb", required=True)
    parser.add_argument("--motif_tsv", required=True)
    parser.add_argument("--stage", default="all", choices=["all"] + STAGE_ORDER)
    parser.add_argument("--run", action="store_true", help="Execute planned commands. Default only writes manifests.")
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--rfd3_json", default="")
    parser.add_argument("--complex_pdb", default="", help="Optional source complex PDB for motif_extraction.")
    parser.add_argument("--motif_ranges", default="", help="Optional ranges for motif_extraction, e.g. A163-181.")
    parser.add_argument("--motif_name", default="epitope_motif")
    parser.add_argument("--prediction_json_dir", default="")
    parser.add_argument("--prediction_pdb_dir", default="")
    parser.add_argument("--filter_summary_csv", default="")
    parser.add_argument("--sequence_fasta", default="")
    parser.add_argument("--final_dir", default="")
    parser.add_argument("--backup_dir", default="")
    parser.add_argument("--backend_root", default="")
    parser.add_argument("--shortlist_csv", default="")
    parser.add_argument("--consensus_csv", default="")
    parser.add_argument("--top_consensus_csv", default="")
    parser.add_argument("--cross_model_root", default="")
    parser.add_argument("--package_out_dir", default="")
    parser.add_argument("--candidate_ids", default="design_1,design_9,design_4")
    parser.add_argument("--source_backend", default="RFdiffusion v1")
    parser.add_argument("--min_plddt", type=float, default=70.0)
    parser.add_argument("--max_pae", type=float, default=10.0)
    parser.add_argument("--max_motif_rmsd", type=float, default=1.5)
    parser.add_argument("--max_clashes", type=int, default=20)
    args = parser.parse_args()

    commands = build_commands(args)
    write_manifest(args, commands)
    print("Wrote workflow_manifest.json and workflow_commands.tsv in %s" % args.work_dir)
    if args.run:
        for cmd in commands:
            print("RUN %s: %s" % (cmd["stage"], " ".join(shlex.quote(part) for part in cmd["argv"])))
            subprocess.run(cmd["argv"], check=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
