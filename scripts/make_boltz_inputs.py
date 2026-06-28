#!/usr/bin/env python3
"""Translate canonical prediction inputs to Boltz native YAML inputs."""

import argparse
import csv
import json
from pathlib import Path
from typing import Dict, List, Optional


def read_tsv(path: Optional[Path]) -> List[Dict[str, str]]:
    if not path or not path.exists():
        return []
    with path.open("r", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def quote_yaml(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return '"%s"' % escaped


def canonical_paths(args: argparse.Namespace) -> List[Path]:
    paths = []
    if args.canonical_json:
        paths.append(Path(args.canonical_json))
    if args.canonical_manifest:
        for row in read_tsv(Path(args.canonical_manifest)):
            value = row.get("canonical_json")
            if value:
                paths.append(Path(value))
    return paths


def msa_index(rows: List[Dict[str, str]]) -> Dict[tuple, Dict[str, str]]:
    return {(row.get("job_name", ""), row.get("chain_id", "")): row for row in rows}


def write_boltz_yaml(payload: Dict, stage1: Dict[tuple, Dict[str, str]], out_path: Path) -> None:
    lines = ["version: 1", "sequences:"]
    job_name = payload["job_name"]
    for chain in payload.get("chains", []):
        chain_id = chain.get("chain_id", "A")
        lines.append("  - protein:")
        lines.append("      id: %s" % quote_yaml(chain_id))
        lines.append("      sequence: %s" % quote_yaml(chain["sequence"]))
        msa_row = stage1.get((job_name, chain_id)) or stage1.get(("", chain_id)) or {}
        msa_path = msa_row.get("unpaired_msa") or msa_row.get("paired_msa") or ""
        if msa_path:
            lines.append("      msa: %s" % quote_yaml(msa_path))
        else:
            lines.append("      msa: empty")
    lines.append("properties: []")
    out_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical_json", default="")
    parser.add_argument("--canonical_manifest", default="")
    parser.add_argument("--af3_stage1_manifest", default="", help="Optional extracted AF3 Stage 1 asset manifest TSV.")
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--manifest", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage1 = msa_index(read_tsv(Path(args.af3_stage1_manifest) if args.af3_stage1_manifest else None))
    rows = []
    for canonical_json in canonical_paths(args):
        payload = json.loads(canonical_json.read_text())
        job_name = payload["job_name"]
        yaml_path = out_dir / (job_name + ".boltz.yaml")
        write_boltz_yaml(payload, stage1, yaml_path)
        rows.append({
            "job_name": job_name,
            "canonical_json": str(canonical_json.resolve()),
            "boltz_yaml": str(yaml_path.resolve()),
        })

    if not rows:
        raise SystemExit("no canonical inputs found")
    manifest = Path(args.manifest) if args.manifest else out_dir / "boltz_input_manifest.tsv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["job_name", "canonical_json", "boltz_yaml"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote %d Boltz YAML inputs to %s" % (len(rows), out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
