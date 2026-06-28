#!/usr/bin/env python3
"""Convert ProteinMPNN FASTA outputs into AlphaFold3 JSON input files."""

import argparse
import csv
import json
import os
import re


def sanitize_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:120] or "design"


def parse_mpnn_score(header):
    match = re.search(r"(?:^|[, ])score=([-+]?[0-9]*\.?[0-9]+)", header)
    if not match:
        return None
    return float(match.group(1))


def read_fasta(path):
    name = None
    chunks = []
    with open(path, "r") as handle:
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
                chunks.append(line.strip())
        if name and chunks:
            yield name, "".join(chunks)


def read_tsv(path):
    with open(path, "r", newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def canonical_records(args):
    paths = []
    if args.canonical_json:
        paths.append(args.canonical_json)
    if args.canonical_manifest:
        for row in read_tsv(args.canonical_manifest):
            if row.get("canonical_json"):
                paths.append(row["canonical_json"])
    for path in paths:
        with open(path, "r") as handle:
            payload = json.load(handle)
        chains = payload.get("chains", [])
        if not chains:
            continue
        yield {
            "job_name": payload["job_name"],
            "source_name": payload.get("source_fasta_header", payload["job_name"]),
            "score": payload.get("mpnn_score"),
            "chains": chains,
        }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fasta", default="", help="ProteinMPNN FASTA file or combined FASTA.")
    parser.add_argument("--out_dir", required=True, help="Directory for AF3 JSON input files.")
    parser.add_argument("--canonical_json", default="", help="Optional canonical prediction JSON; overrides --fasta when set.")
    parser.add_argument("--canonical_manifest", default="", help="Optional canonical_manifest.tsv; overrides --fasta when set.")
    parser.add_argument("--chain_id", default="A")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--skip_first", action="store_true", help="Skip the first FASTA record, usually the input backbone/native sequence in ProteinMPNN output.")
    parser.add_argument("--max_records", type=int, default=0, help="Maximum records to write after skipping; 0 means no limit.")
    parser.add_argument("--name_prefix", default="", help="Optional prefix for generated job names.")
    parser.add_argument("--manifest", default="", help="Optional TSV manifest path to write.")
    parser.add_argument("--query_only", action="store_true", help="Embed empty MSA/template fields so AF3 can run with --run_data_pipeline=False.")
    parser.add_argument("--sort_by_score", action="store_true", help="Sort ProteinMPNN design records by ascending score before taking max_records.")
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    count = 0
    manifest_rows = []
    if args.canonical_json or args.canonical_manifest:
        selected = list(canonical_records(args))
        if args.max_records:
            selected = selected[:args.max_records]
        records = [
            (
                item["job_name"],
                item["source_name"],
                item["score"],
                [
                    {
                        "id": chain.get("chain_id", args.chain_id),
                        "sequence": chain["sequence"],
                    }
                    for chain in item["chains"]
                    if chain.get("molecule_type", "protein") == "protein"
                ],
            )
            for item in selected
        ]
    else:
        if not args.fasta:
            raise SystemExit("provide --fasta, --canonical_json, or --canonical_manifest")
        records = []
        for idx, (name, sequence) in enumerate(read_fasta(args.fasta)):
            if args.skip_first and idx == 0:
                continue
            records.append((name, sequence, parse_mpnn_score(name)))
        if args.sort_by_score:
            records.sort(key=lambda row: (row[2] is None, row[2] if row[2] is not None else 999999.0, row[0]))
        records = [
            (
                sanitize_name((args.name_prefix + "_" if args.name_prefix else "") + name),
                name,
                score,
                [{"id": args.chain_id, "sequence": sequence}],
            )
            for name, sequence, score in records
        ]

    for job_name, source_name, score, chains in records:
        if args.max_records and count >= args.max_records:
            break
        af3_sequences = []
        for chain in chains:
            protein = {"id": chain["id"], "sequence": chain["sequence"]}
            if args.query_only:
                protein.update({"unpairedMsa": "", "pairedMsa": "", "templates": []})
            af3_sequences.append({"protein": protein})
        payload = {
            "name": job_name,
            "modelSeeds": [args.seed],
            "sequences": af3_sequences,
            "dialect": "alphafold3",
            "version": 1,
        }
        out_path = os.path.join(args.out_dir, job_name + ".json")
        with open(out_path, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        score_text = "" if score is None else str(score)
        chain_ids = ",".join(chain["id"] for chain in chains)
        total_length = sum(len(chain["sequence"]) for chain in chains)
        manifest_rows.append((job_name, source_name, score_text, chain_ids, total_length, out_path))
        count += 1
    if args.manifest:
        with open(args.manifest, "w") as handle:
            handle.write("job_name\tsource_name\tmpnn_score\tchain_id\tsequence_length\tjson_path\n")
            for row in manifest_rows:
                handle.write("%s\t%s\t%s\t%s\t%s\t%s\n" % row)
    print("Wrote %d AF3 JSON input files to %s" % (count, args.out_dir))
    if count == 0:
        raise SystemExit("no FASTA records were written to AF3 JSON")


if __name__ == "__main__":
    main()
