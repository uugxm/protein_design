#!/usr/bin/env python3
"""Extract stable assets from AF3 Stage 1 data-pipeline outputs.

AF3 *_data.json files are retained for AF3 Stage 2 only. This script writes a
separate manifest of chain sequences, optional MSA files, and template metadata
so other predictors can consume stable assets without depending on AF3 internals.
"""

import argparse
import csv
import json
import re
import shutil
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


def safe_name(text: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_") or "item"


def find_data_jsons(root: Path) -> List[Path]:
    hits = []
    for path in sorted(root.rglob("*.json")):
        lower = path.name.lower()
        if lower.endswith("_data.json") or lower.endswith("data.json") or "data" in lower:
            hits.append(path)
    return hits


def protein_entries(payload: Any) -> Iterable[Dict[str, Any]]:
    if isinstance(payload, dict):
        sequences = payload.get("sequences")
        if isinstance(sequences, list):
            for item in sequences:
                if isinstance(item, dict) and isinstance(item.get("protein"), dict):
                    yield item["protein"]
        if isinstance(payload.get("protein"), dict):
            yield payload["protein"]
        for value in payload.values():
            if isinstance(value, (dict, list)):
                yield from protein_entries(value)
    elif isinstance(payload, list):
        for item in payload:
            yield from protein_entries(item)


def first_value(entry: Dict[str, Any], names: List[str]) -> Any:
    for name in names:
        if name in entry:
            return entry[name]
    return None


def write_msa(content: Any, path: Path) -> str:
    if not content:
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(content, list):
        text = "\n".join(str(item) for item in content if item is not None)
    else:
        text = str(content)
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text)
    return str(path.resolve())


def summarize_templates(templates: Any, path: Path) -> str:
    if templates in (None, "", []):
        return ""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(templates, indent=2, sort_keys=True) + "\n")
    return str(path.resolve())


def parse_one(data_json: Path, out_dir: Path, keep_raw: bool) -> List[Dict[str, str]]:
    rows = []
    job_name = safe_name(data_json.stem.replace("_data", ""))
    raw_path = ""
    if keep_raw:
        raw_dir = out_dir / "raw_af3_data"
        raw_dir.mkdir(parents=True, exist_ok=True)
        target = raw_dir / data_json.name
        shutil.copy2(data_json, target)
        raw_path = str(target.resolve())

    try:
        payload = json.loads(data_json.read_text())
    except Exception as exc:
        return [{
            "job_name": job_name,
            "chain_id": "",
            "sequence": "",
            "unpaired_msa": "",
            "paired_msa": "",
            "template_metadata": "",
            "raw_af3_data_json": raw_path or str(data_json.resolve()),
            "parse_status": "json_parse_error:%r" % (exc,),
        }]

    proteins = list(protein_entries(payload))
    if not proteins:
        return [{
            "job_name": job_name,
            "chain_id": "",
            "sequence": "",
            "unpaired_msa": "",
            "paired_msa": "",
            "template_metadata": "",
            "raw_af3_data_json": raw_path or str(data_json.resolve()),
            "parse_status": "raw_manifest_only:no_protein_entries",
        }]

    for index, protein in enumerate(proteins, start=1):
        chain_value = first_value(protein, ["id", "chain_id", "chainId", "chain"])
        if isinstance(chain_value, list):
            chain_id = str(chain_value[0]) if chain_value else chr(64 + index)
        else:
            chain_id = str(chain_value or chr(64 + index))
        sequence = str(first_value(protein, ["sequence", "seq"]) or "")
        prefix = "%s_%s" % (job_name, safe_name(chain_id))
        unpaired = first_value(protein, ["unpairedMsa", "unpaired_msa", "unpaired_msa_a3m"])
        paired = first_value(protein, ["pairedMsa", "paired_msa", "paired_msa_a3m"])
        templates = first_value(protein, ["templates", "template_features", "templateMetadata"])
        rows.append({
            "job_name": job_name,
            "chain_id": chain_id,
            "sequence": sequence,
            "unpaired_msa": write_msa(unpaired, out_dir / "msa" / (prefix + "_unpaired.a3m")),
            "paired_msa": write_msa(paired, out_dir / "msa" / (prefix + "_paired.a3m")),
            "template_metadata": summarize_templates(templates, out_dir / "templates" / (prefix + "_templates.json")),
            "raw_af3_data_json": raw_path or str(data_json.resolve()),
            "parse_status": "ok",
        })
    return rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_dir", required=True, help="AF3 Stage 1 output directory.")
    parser.add_argument("--out_dir", required=True, help="Directory for extracted stable assets.")
    parser.add_argument("--manifest", default="", help="Optional manifest TSV path.")
    parser.add_argument("--no_keep_raw", action="store_true", help="Do not copy raw *_data.json files.")
    args = parser.parse_args()

    root = Path(args.input_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    data_jsons = find_data_jsons(root)
    rows: List[Dict[str, str]] = []
    for path in data_jsons:
        rows.extend(parse_one(path, out_dir, keep_raw=not args.no_keep_raw))
    if not rows:
        rows.append({
            "job_name": "",
            "chain_id": "",
            "sequence": "",
            "unpaired_msa": "",
            "paired_msa": "",
            "template_metadata": "",
            "raw_af3_data_json": "",
            "parse_status": "no_af3_data_json_found",
        })

    manifest = Path(args.manifest) if args.manifest else out_dir / "af3_stage1_asset_manifest.tsv"
    with manifest.open("w", newline="") as handle:
        fieldnames = [
            "job_name", "chain_id", "sequence", "unpaired_msa", "paired_msa",
            "template_metadata", "raw_af3_data_json", "parse_status",
        ]
        writer = csv.DictWriter(handle, fieldnames=fieldnames, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)
    print("Wrote AF3 Stage 1 asset manifest with %d rows to %s" % (len(rows), manifest))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
