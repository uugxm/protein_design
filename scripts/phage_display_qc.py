#!/usr/bin/env python3
"""Sequence-level QC for phage-display-ready scaffold candidates."""

import argparse
import csv
import re
from pathlib import Path
from typing import Dict, Iterable, List, Tuple

from pre_order_qc import CANONICAL_AA, glyco_motifs, hydrophobic_stretches, low_complexity_regions, repetitive_regions


def read_fasta(path: Path) -> Iterable[Tuple[str, str]]:
    name = None
    chunks: List[str] = []
    with path.open("r") as handle:
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
                chunks.append(line)
        if name and chunks:
            yield name, "".join(chunks)


def read_sequences(args) -> List[Tuple[str, str]]:
    if args.fasta:
        return list(read_fasta(Path(args.fasta)))
    rows = []
    with Path(args.sequence_csv).open("r", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row[args.id_column], row[args.sequence_column]))
    return rows


def polybasic_runs(seq: str) -> List[str]:
    return ["%s%d-%d" % (m.group(0), m.start() + 1, m.end()) for m in re.finditer(r"[KR]{5,}", seq)]


def qc_row(design_id: str, seq: str, args) -> Dict[str, object]:
    seq = seq.strip().upper()
    noncanonical = sorted(set(seq) - CANONICAL_AA)
    flags = []
    if not seq:
        flags.append("missing_sequence")
    if noncanonical:
        flags.append("noncanonical_residues")
    if len(seq) < args.min_length:
        flags.append("short_insert")
    if len(seq) > args.max_length:
        flags.append("long_insert")
    if seq.count("C") > args.max_cysteines:
        flags.append("cysteine_count_above_limit")
    glyco = glyco_motifs(seq)
    hydro = hydrophobic_stretches(seq, min_len=args.hydrophobic_run)
    low_complexity = low_complexity_regions(seq) + repetitive_regions(seq)
    polybasic = polybasic_runs(seq)
    if glyco:
        flags.append("nxs_t_motif")
    if hydro:
        flags.append("hydrophobic_run")
    if low_complexity:
        flags.append("low_complexity_or_repeat")
    if polybasic:
        flags.append("polybasic_run")
    return {
        "design_id": design_id,
        "sequence_length": len(seq),
        "cysteine_count": seq.count("C"),
        "noncanonical_residues": ";".join(noncanonical),
        "nxs_t_motifs": ";".join(glyco),
        "hydrophobic_runs": ";".join(hydro),
        "low_complexity_or_repeats": ";".join(low_complexity),
        "polybasic_runs": ";".join(polybasic),
        "phage_display_status": "PASS" if not flags else "REVIEW",
        "flags": ";".join(flags) if flags else "none",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fasta", default="", help="Input FASTA of displayed scaffold inserts.")
    parser.add_argument("--sequence_csv", default="", help="Alternative CSV containing design IDs and sequences.")
    parser.add_argument("--id_column", default="design_id")
    parser.add_argument("--sequence_column", default="amino_acid_sequence")
    parser.add_argument("--output_csv", required=True, help="QC table to write.")
    parser.add_argument("--min_length", type=int, default=40)
    parser.add_argument("--max_length", type=int, default=250)
    parser.add_argument("--max_cysteines", type=int, default=2)
    parser.add_argument("--hydrophobic_run", type=int, default=7)
    args = parser.parse_args()

    if not args.fasta and not args.sequence_csv:
        raise SystemExit("provide --fasta or --sequence_csv")
    rows = [qc_row(design_id, seq, args) for design_id, seq in read_sequences(args)]
    if not rows:
        rows = [qc_row("", "", args)]
    out = Path(args.output_csv)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
