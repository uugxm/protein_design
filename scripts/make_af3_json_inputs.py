#!/usr/bin/env python3
"""Convert ProteinMPNN FASTA outputs into AlphaFold3 JSON input files."""

import argparse
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


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--fasta", required=True, help="ProteinMPNN FASTA file or combined FASTA.")
    parser.add_argument("--out_dir", required=True, help="Directory for AF3 JSON input files.")
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
    records = []
    for idx, (name, sequence) in enumerate(read_fasta(args.fasta)):
        if args.skip_first and idx == 0:
            continue
        records.append((name, sequence, parse_mpnn_score(name)))
    if args.sort_by_score:
        records.sort(key=lambda row: (row[2] is None, row[2] if row[2] is not None else 999999.0, row[0]))

    for name, sequence, score in records:
        if args.max_records and count >= args.max_records:
            break
        prefix = args.name_prefix + "_" if args.name_prefix else ""
        job_name = sanitize_name(prefix + name)
        protein = {"id": args.chain_id, "sequence": sequence}
        if args.query_only:
            protein.update({"unpairedMsa": "", "pairedMsa": "", "templates": []})
        payload = {
            "name": job_name,
            "modelSeeds": [args.seed],
            "sequences": [{"protein": protein}],
            "dialect": "alphafold3",
            "version": 1,
        }
        out_path = os.path.join(args.out_dir, job_name + ".json")
        with open(out_path, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        score_text = "" if score is None else str(score)
        manifest_rows.append((job_name, name, score_text, args.chain_id, len(sequence), out_path))
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
