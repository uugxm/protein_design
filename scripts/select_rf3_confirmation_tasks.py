#!/usr/bin/env python3
"""Select top AF3 designs and write RF3 confirmation task manifests."""

import argparse
import csv
from pathlib import Path
from typing import Dict, List


def to_float(value, default):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def sort_key(row: Dict[str, str]):
    return (
        0 if row.get("pass") == "PASS" else 1,
        -to_float(row.get("plddt_mean"), -1.0),
        to_float(row.get("pae_mean"), 999999.0),
        to_float(row.get("motif_rmsd"), 999999.0),
        to_float(row.get("clash_count"), 999999.0),
        row.get("design_id") or row.get("backbone_id", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--af3_summary", required=True)
    parser.add_argument("--run_dir", required=True)
    parser.add_argument("--output_tsv", required=True)
    parser.add_argument("--top_n", type=int, default=5)
    args = parser.parse_args()

    run_dir = Path(args.run_dir)
    rows = sorted(read_csv(Path(args.af3_summary)), key=sort_key)[: args.top_n]
    fieldnames = [
        "design_id",
        "canonical_manifest",
        "backbone_pdb",
        "trb_path",
        "af3_pass",
        "af3_plddt",
        "af3_pae",
        "af3_motif_rmsd",
    ]
    out_rows = []
    for row in rows:
        design_id = row.get("design_id") or row.get("backbone_id")
        task_dir = run_dir / "array_work" / design_id
        out_rows.append({
            "design_id": design_id,
            "canonical_manifest": str(task_dir / "prediction_inputs" / "canonical" / "canonical_manifest.tsv"),
            "backbone_pdb": str(run_dir / "rfdiffusion_outputs" / ("%s.pdb" % design_id)),
            "trb_path": str(run_dir / "rfdiffusion_outputs" / ("%s.trb" % design_id)),
            "af3_pass": row.get("pass", ""),
            "af3_plddt": row.get("plddt_mean", ""),
            "af3_pae": row.get("pae_mean", ""),
            "af3_motif_rmsd": row.get("motif_rmsd", ""),
        })

    output = Path(args.output_tsv)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t", lineterminator="\n")
        writer.writeheader()
        writer.writerows(out_rows)
    print("Wrote %d RF3 task rows to %s" % (len(out_rows), output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
