#!/usr/bin/env python3
"""Translate canonical prediction inputs to Foundry RF3 JSON inputs."""

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


def msa_index(rows: List[Dict[str, str]]) -> Dict[tuple, Dict[str, str]]:
    out = {}
    for row in rows:
        out[(row.get("job_name", ""), row.get("chain_id", ""))] = row
    return out


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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--canonical_json", default="")
    parser.add_argument("--canonical_manifest", default="")
    parser.add_argument("--af3_stage1_manifest", default="", help="Optional extracted AF3 Stage 1 asset manifest TSV.")
    parser.add_argument("--out_dir", required=True)
    parser.add_argument("--manifest", default="")
    parser.add_argument("--prefer_paired_msa", action="store_true")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    stage1 = msa_index(read_tsv(Path(args.af3_stage1_manifest) if args.af3_stage1_manifest else None))
    rows = []
    for canonical_json in canonical_paths(args):
        payload = json.loads(canonical_json.read_text())
        job_name = payload["job_name"]
        components = []
        for chain in payload.get("chains", []):
            chain_id = chain.get("chain_id", "A")
            component = {
                "seq": chain["sequence"],
                "chain_id": chain_id,
            }
            msa_row = stage1.get((job_name, chain_id)) or stage1.get(("", chain_id)) or {}
            msa_path = ""
            if args.prefer_paired_msa:
                msa_path = msa_row.get("paired_msa") or msa_row.get("unpaired_msa") or ""
            else:
                msa_path = msa_row.get("unpaired_msa") or msa_row.get("paired_msa") or ""
            if msa_path:
                component["msa_path"] = msa_path
            components.append(component)
        rf3_payload = {
            "name": job_name,
            "components": components,
            "metadata": {
                "source_schema": payload.get("schema", ""),
                "canonical_json": str(canonical_json.resolve()),
                "reference_pdb": payload.get("reference_pdb", ""),
                "motif_tsv": payload.get("motif_tsv", ""),
                "note": "Generated from canonical prediction input; no AF3 *_data.json fields were consumed.",
            },
        }
        out_path = out_dir / (job_name + ".rf3.json")
        out_path.write_text(json.dumps(rf3_payload, indent=2, sort_keys=True) + "\n")
        rows.append({
            "job_name": job_name,
            "canonical_json": str(canonical_json.resolve()),
            "rf3_json": str(out_path.resolve()),
            "chains": ",".join(chain.get("chain_id", "") for chain in payload.get("chains", [])),
        })

    if not rows:
        raise SystemExit("no canonical inputs found")
    manifest = Path(args.manifest) if args.manifest else out_dir / "rf3_input_manifest.tsv"
    with manifest.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["job_name", "canonical_json", "rf3_json", "chains"], delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote %d RF3 JSON inputs to %s" % (len(rows), out_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
