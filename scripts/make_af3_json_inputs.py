#!/usr/bin/env python3
"""Convert ProteinMPNN FASTA outputs into AlphaFold3 JSON input files."""

import argparse
import json
import os
import re


def sanitize_name(text):
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", text).strip("_")[:120] or "design"


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
                name = line[1:].split()[0]
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
    args = parser.parse_args()

    os.makedirs(args.out_dir, exist_ok=True)
    count = 0
    for name, sequence in read_fasta(args.fasta):
        job_name = sanitize_name(name)
        payload = {
            "name": job_name,
            "modelSeeds": [args.seed],
            "sequences": [{"protein": {"id": args.chain_id, "sequence": sequence}}],
            "dialect": "alphafold3",
            "version": 1,
        }
        out_path = os.path.join(args.out_dir, job_name + ".json")
        with open(out_path, "w") as handle:
            json.dump(payload, handle, indent=2, sort_keys=True)
            handle.write("\n")
        count += 1
    print("Wrote %d AF3 JSON input files to %s" % (count, args.out_dir))


if __name__ == "__main__":
    main()
