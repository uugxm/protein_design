#!/usr/bin/env python3
"""Select backbones for downstream MPNN/AF3 from raw motif audit rows."""

import argparse
import csv
import math
from pathlib import Path
from typing import Dict, List, Optional


def read_csv(path: Path) -> List[Dict[str, str]]:
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle))


def to_float(value) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        val = float(value)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(val) else val


def sort_key(row: Dict[str, str]):
    rmsd = to_float(row.get("raw_backbone_motif_rmsd"))
    missing = to_float(row.get("motif_atoms_missing")) or 999999.0
    clashes = to_float(row.get("raw_backbone_clash_count_around_motif")) or 999999.0
    support = to_float(row.get("local_support_residue_count")) or 0.0
    return (
        missing,
        rmsd if rmsd is not None else 999999.0,
        clashes,
        -support,
        row.get("design_id", ""),
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audit_csv", required=True)
    parser.add_argument("--output_list", required=True)
    parser.add_argument("--output_tsv", default="")
    parser.add_argument("--top_n", type=int, default=20)
    args = parser.parse_args()

    rows = sorted(read_csv(Path(args.audit_csv)), key=sort_key)
    selected = rows[: args.top_n]
    output = Path(args.output_list)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("".join(row["raw_backbone_pdb"] + "\n" for row in selected))
    if args.output_tsv:
        tsv = Path(args.output_tsv)
        tsv.parent.mkdir(parents=True, exist_ok=True)
        fields = ["rank"] + list(rows[0].keys()) if rows else ["rank"]
        with tsv.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", extrasaction="ignore", lineterminator="\n")
            writer.writeheader()
            for idx, row in enumerate(selected, start=1):
                item = dict(row)
                item["rank"] = idx
                writer.writerow(item)
    print("Selected %d backbones into %s" % (len(selected), output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
