#!/usr/bin/env python3
"""Extract antigen epitope residues from an antigen-antibody complex.

The script intentionally avoids heavy structural dependencies so it can run on
cluster login nodes for input preparation. It supports standard PDB files and
RCSB mmCIF atom_site loops, using author chain IDs for mmCIF inputs.
"""

import argparse
import csv
import math
import re
import shlex
from collections import OrderedDict, defaultdict
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple


AA3_TO_1 = {
    "ALA": "A", "ARG": "R", "ASN": "N", "ASP": "D", "CYS": "C",
    "GLN": "Q", "GLU": "E", "GLY": "G", "HIS": "H", "ILE": "I",
    "LEU": "L", "LYS": "K", "MET": "M", "PHE": "F", "PRO": "P",
    "SER": "S", "THR": "T", "TRP": "W", "TYR": "Y", "VAL": "V",
}

HEAVY_ELEMENTS = {"C", "N", "O", "S", "P", "SE"}


def residue_key(atom: Dict[str, object]) -> Tuple[str, int, str]:
    return (str(atom["chain"]), int(atom["resseq"]), str(atom.get("icode", "")))


def residue_label(key: Tuple[str, int, str]) -> str:
    chain, resseq, icode = key
    return "%s%d%s" % (chain, resseq, icode)


def squared_distance(a: Sequence[float], b: Sequence[float]) -> float:
    return sum((float(a[i]) - float(b[i])) ** 2 for i in range(3))


def infer_element(atom_name: str, element: str = "") -> str:
    if element and element not in (".", "?"):
        return element.strip().upper()
    cleaned = re.sub(r"[^A-Za-z]", "", atom_name).upper()
    if cleaned.startswith("SE"):
        return "SE"
    return cleaned[:1] or "?"


def is_heavy_atom(atom: Dict[str, object]) -> bool:
    element = infer_element(str(atom.get("atom", "")), str(atom.get("element", "")))
    return element in HEAVY_ELEMENTS and element != "H"


def parse_pdb(path: Path) -> Tuple[List[Dict[str, object]], List[str]]:
    atoms = []
    header = []
    for raw in path.read_text(errors="ignore").splitlines():
        rec = raw[:6].strip()
        if rec in {"ATOM", "HETATM"}:
            altloc = raw[16:17].strip()
            if altloc not in ("", "A", "1"):
                continue
            try:
                atoms.append({
                    "record": rec,
                    "serial": int(raw[6:11]),
                    "atom": raw[12:16].strip(),
                    "altloc": altloc,
                    "resname": raw[17:20].strip(),
                    "chain": raw[21:22].strip() or "_",
                    "resseq": int(raw[22:26]),
                    "icode": raw[26:27].strip(),
                    "coord": (float(raw[30:38]), float(raw[38:46]), float(raw[46:54])),
                    "occupancy": raw[54:60].strip() or "1.00",
                    "bfactor": raw[60:66].strip() or "0.00",
                    "element": infer_element(raw[12:16].strip(), raw[76:78].strip()),
                    "raw": raw,
                })
            except ValueError:
                continue
        else:
            header.append(raw)
    return atoms, header


def read_cif_loop(lines: List[str], start: int) -> Tuple[List[str], List[List[str]], int]:
    columns = []
    rows = []
    idx = start + 1
    while idx < len(lines) and lines[idx].strip().startswith("_"):
        columns.append(lines[idx].strip())
        idx += 1
    while idx < len(lines):
        line = lines[idx].strip()
        if not line:
            idx += 1
            continue
        if line == "#" or line.startswith("loop_") or line.startswith("_"):
            break
        rows.append(shlex.split(line))
        idx += 1
    return columns, rows, idx


def parse_mmcif(path: Path) -> Tuple[List[Dict[str, object]], List[str]]:
    lines = path.read_text(errors="ignore").splitlines()
    atoms = []
    idx = 0
    while idx < len(lines):
        if lines[idx].strip() != "loop_":
            idx += 1
            continue
        columns, rows, next_idx = read_cif_loop(lines, idx)
        idx = next_idx
        if not columns or "_atom_site.group_PDB" not in columns:
            continue
        col = {name: pos for pos, name in enumerate(columns)}

        def get(row, name, default=""):
            pos = col.get(name)
            if pos is None or pos >= len(row):
                return default
            value = row[pos]
            return "" if value in (".", "?") else value

        for row in rows:
            group = get(row, "_atom_site.group_PDB")
            if group not in {"ATOM", "HETATM"}:
                continue
            altloc = get(row, "_atom_site.label_alt_id")
            if altloc not in ("", "A", "1"):
                continue
            try:
                atoms.append({
                    "record": group,
                    "serial": int(get(row, "_atom_site.id", "0")),
                    "atom": get(row, "_atom_site.auth_atom_id") or get(row, "_atom_site.label_atom_id"),
                    "altloc": altloc,
                    "resname": get(row, "_atom_site.auth_comp_id") or get(row, "_atom_site.label_comp_id"),
                    "chain": get(row, "_atom_site.auth_asym_id") or get(row, "_atom_site.label_asym_id") or "_",
                    "resseq": int(float(get(row, "_atom_site.auth_seq_id") or get(row, "_atom_site.label_seq_id"))),
                    "icode": get(row, "_atom_site.pdbx_PDB_ins_code"),
                    "coord": (
                        float(get(row, "_atom_site.Cartn_x")),
                        float(get(row, "_atom_site.Cartn_y")),
                        float(get(row, "_atom_site.Cartn_z")),
                    ),
                    "occupancy": get(row, "_atom_site.occupancy", "1.00"),
                    "bfactor": get(row, "_atom_site.B_iso_or_equiv", "0.00"),
                    "element": infer_element(get(row, "_atom_site.label_atom_id"), get(row, "_atom_site.type_symbol")),
                    "raw": "",
                })
            except ValueError:
                continue
    return atoms, lines


def read_structure(path: Path) -> Tuple[List[Dict[str, object]], List[str]]:
    suffix = path.suffix.lower()
    if suffix in {".cif", ".mmcif"}:
        return parse_mmcif(path)
    return parse_pdb(path)


def atom_to_pdb_line(serial: int, atom: Dict[str, object]) -> str:
    atom_name = str(atom["atom"])[:4]
    resname = str(atom["resname"])[:3]
    chain = str(atom["chain"])[:1] or "_"
    icode = str(atom.get("icode", ""))[:1]
    x, y, z = atom["coord"]
    return (
        "ATOM  %5d %-4s %3s %1s%4d%1s   %8.3f%8.3f%8.3f%6s%6s          %2s"
        % (
            serial,
            atom_name,
            resname,
            chain,
            int(atom["resseq"]),
            icode,
            float(x),
            float(y),
            float(z),
            str(atom.get("occupancy", "1.00"))[:6].rjust(6),
            str(atom.get("bfactor", "0.00"))[:6].rjust(6),
            infer_element(atom_name, str(atom.get("element", "")))[:2].rjust(2),
        )
    )


def write_pdb(path: Path, atoms: Iterable[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w") as handle:
        serial = 1
        last_chain = None
        for atom in atoms:
            chain = atom["chain"]
            if last_chain is not None and chain != last_chain:
                handle.write("TER\n")
            handle.write(atom_to_pdb_line(serial, atom) + "\n")
            serial += 1
            last_chain = chain
        handle.write("TER\nEND\n")


def residue_order(atoms: Iterable[Dict[str, object]]) -> OrderedDict:
    residues = OrderedDict()
    for atom in atoms:
        key = residue_key(atom)
        residues.setdefault(key, str(atom["resname"]))
    return residues


def parse_residue_spec(spec: str) -> set:
    """Parse comma/space specs like A163,A170-171 or a TSV path."""
    wanted = set()
    if not spec:
        return wanted
    maybe_path = Path(spec)
    if maybe_path.exists():
        with maybe_path.open("r", newline="") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            if reader.fieldnames:
                for row in reader:
                    chain = row.get("chain") or row.get("chain_id")
                    residue = row.get("residue") or row.get("position")
                    start = row.get("start")
                    end = row.get("end")
                    if chain and residue:
                        wanted.add((chain, int(residue), ""))
                    elif chain and start and end:
                        for resseq in range(int(start), int(end) + 1):
                            wanted.add((chain, resseq, ""))
        return wanted
    for token in re.split(r"[,\s/]+", spec.strip()):
        if not token:
            continue
        match = re.match(r"^([A-Za-z0-9_])(\d+)(?:-(\d+))?$", token)
        if not match:
            raise SystemExit("Cannot parse residue spec token: %s" % token)
        chain, start, end = match.group(1), int(match.group(2)), match.group(3)
        end_i = int(end) if end else start
        for resseq in range(start, end_i + 1):
            wanted.add((chain, resseq, ""))
    return wanted


def normalize_spec_set(spec_set: set, observed: Iterable[Tuple[str, int, str]]) -> set:
    observed = set(observed)
    exact = spec_set & observed
    no_icode = {(chain, resseq, "") for chain, resseq, _icode in observed}
    out = set(exact)
    for key in spec_set:
        if key in no_icode:
            chain, resseq, _ = key
            for obs in observed:
                if obs[0] == chain and obs[1] == resseq:
                    out.add(obs)
    return out


def contact_rows(
    atoms: List[Dict[str, object]],
    antigen_chain: str,
    heavy_chain: str,
    light_chain: str,
    cutoff: float,
) -> List[Dict[str, object]]:
    cutoff2 = cutoff * cutoff
    antigen_atoms = [a for a in atoms if a["chain"] == antigen_chain and a["record"] == "ATOM" and is_heavy_atom(a)]
    antibody_atoms = [
        a for a in atoms
        if a["chain"] in {heavy_chain, light_chain} and a["record"] == "ATOM" and is_heavy_atom(a)
    ]
    rows = []
    for ag in antigen_atoms:
        for ab in antibody_atoms:
            d2 = squared_distance(ag["coord"], ab["coord"])
            if d2 <= cutoff2:
                role = "heavy" if ab["chain"] == heavy_chain else "light"
                rows.append({
                    "cutoff_angstrom": "%.2f" % cutoff,
                    "antigen_chain": ag["chain"],
                    "antigen_residue": ag["resseq"],
                    "antigen_icode": ag.get("icode", ""),
                    "antigen_resname": ag["resname"],
                    "antigen_atom": ag["atom"],
                    "antibody_chain": ab["chain"],
                    "antibody_role": role,
                    "antibody_residue": ab["resseq"],
                    "antibody_icode": ab.get("icode", ""),
                    "antibody_resname": ab["resname"],
                    "antibody_atom": ab["atom"],
                    "distance_angstrom": "%.3f" % math.sqrt(d2),
                })
    rows.sort(key=lambda row: (
        int(row["antigen_residue"]),
        str(row["antigen_icode"]),
        float(row["distance_angstrom"]),
        str(row["antibody_chain"]),
        int(row["antibody_residue"]),
    ))
    return rows


def summarize_residue_contacts(
    contacts: List[Dict[str, object]],
    residues: OrderedDict,
    whitelist: set,
    blacklist: set,
) -> List[Dict[str, object]]:
    by_residue = defaultdict(list)
    for row in contacts:
        key = (str(row["antigen_chain"]), int(row["antigen_residue"]), str(row["antigen_icode"]))
        by_residue[key].append(row)
    observed = set(residues.keys())
    whitelist = normalize_spec_set(whitelist, observed)
    blacklist = normalize_spec_set(blacklist, observed)
    motif_keys = list(by_residue)
    if whitelist:
        motif_keys = [key for key in motif_keys if key in whitelist]
    if blacklist:
        motif_keys = [key for key in motif_keys if key not in blacklist]
    motif_keys.sort(key=lambda item: (item[0], item[1], item[2]))

    rows = []
    for seq_idx, key in enumerate(motif_keys, start=1):
        hits = by_residue[key]
        min_distance = min(float(row["distance_angstrom"]) for row in hits)
        heavy_hits = [row for row in hits if row["antibody_role"] == "heavy"]
        light_hits = [row for row in hits if row["antibody_role"] == "light"]
        antibody_residues = sorted({
            "%s%d%s" % (row["antibody_chain"], int(row["antibody_residue"]), str(row["antibody_icode"]))
            for row in hits
        })
        resname = residues.get(key, hits[0]["antigen_resname"])
        rows.append({
            "chain": key[0],
            "residue": key[1],
            "icode": key[2],
            "resname": resname,
            "aa": AA3_TO_1.get(str(resname), "X"),
            "motif_index": seq_idx,
            "min_contact_distance_angstrom": "%.3f" % min_distance,
            "heavy_chain_contacts": len(heavy_hits),
            "light_chain_contacts": len(light_hits),
            "total_atom_contacts": len(hits),
            "antibody_contact_residues": ";".join(antibody_residues),
            "provenance": "heavy_atom_contact_cutoff",
        })
    return rows


def segments(rows: List[Dict[str, object]]) -> List[Tuple[int, int]]:
    if not rows:
        return []
    residue_numbers = sorted(int(row["residue"]) for row in rows)
    out = []
    start = prev = residue_numbers[0]
    for resseq in residue_numbers[1:]:
        if resseq == prev + 1:
            prev = resseq
        else:
            out.append((start, prev))
            start = prev = resseq
    out.append((start, prev))
    return out


def write_csv_rows(path: Path, rows: List[Dict[str, object]], fieldnames: List[str], delimiter: str = ",") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore", delimiter=delimiter, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)


def write_summary(path: Path, summary: Dict[str, object]) -> None:
    rows = [{"metric": key, "value": value} for key, value in summary.items()]
    write_csv_rows(path, rows, ["metric", "value"])


def chain_ranges(atoms: Iterable[Dict[str, object]]) -> Dict[str, Tuple[int, int, int]]:
    ranges = {}
    for chain, members in group_atoms_by_chain(atoms).items():
        residues = sorted({int(atom["resseq"]) for atom in members if atom["record"] == "ATOM"})
        if residues:
            ranges[chain] = (residues[0], residues[-1], len(residues))
    return ranges


def group_atoms_by_chain(atoms: Iterable[Dict[str, object]]) -> Dict[str, List[Dict[str, object]]]:
    out = defaultdict(list)
    for atom in atoms:
        out[str(atom["chain"])].append(atom)
    return out


def pdb_header_records(header: List[str], prefix: str) -> List[str]:
    return [line for line in header if line.startswith(prefix)]


def parse_dbref(header: List[str]) -> List[Dict[str, str]]:
    rows = []
    for line in pdb_header_records(header, "DBREF"):
        parts = line.split()
        if len(parts) >= 9:
            rows.append({
                "pdb_chain": parts[2],
                "pdb_start": parts[3],
                "pdb_end": parts[4],
                "database": parts[5],
                "accession": parts[6],
                "database_code": parts[7],
                "db_start": parts[8],
                "db_end": parts[9] if len(parts) > 9 else "",
            })
    return rows


def parse_seqadv_notes(header: List[str]) -> Dict[str, List[str]]:
    notes = defaultdict(list)
    for line in pdb_header_records(header, "SEQADV"):
        chain = line[16:18].strip() or (line.split()[3] if len(line.split()) > 3 else "")
        if chain:
            notes[chain].append(line.strip())
    return notes


def write_chain_mapping(
    path: Path,
    atoms: List[Dict[str, object]],
    header: List[str],
    antigen_chain: str,
    heavy_chain: str,
    light_chain: str,
) -> None:
    ranges = chain_ranges(atoms)
    dbrefs = defaultdict(list)
    for row in parse_dbref(header):
        dbrefs[row["pdb_chain"]].append(row)
    seqadv = parse_seqadv_notes(header)
    role_by_chain = {
        antigen_chain: "antigen",
        heavy_chain: "antibody_heavy",
        light_chain: "antibody_light",
    }
    rows = []
    for chain in sorted(ranges):
        start, end, count = ranges[chain]
        refs = dbrefs.get(chain, [])
        ref_text = ";".join("%s:%s:%s-%s->%s-%s" % (
            ref["database"], ref["accession"], ref["pdb_start"], ref["pdb_end"], ref["db_start"], ref["db_end"]
        ) for ref in refs)
        if chain == antigen_chain:
            region_note = "RSV F residues 27-513; fibritin foldon residues 518-544 if present; expression tag noted by SEQADV"
        elif chain == heavy_chain:
            region_note = "hRSV90 heavy chain"
        elif chain == light_chain:
            region_note = "hRSV90 light chain"
        else:
            region_note = ""
        rows.append({
            "pdb_chain": chain,
            "author_chain": chain,
            "role": role_by_chain.get(chain, "other"),
            "observed_residue_start": start,
            "observed_residue_end": end,
            "observed_residue_count": count,
            "dbref": ref_text,
            "notes": region_note,
            "seqadv_count": len(seqadv.get(chain, [])),
        })
    write_csv_rows(path, rows, [
        "pdb_chain", "author_chain", "role", "observed_residue_start",
        "observed_residue_end", "observed_residue_count", "dbref", "notes", "seqadv_count",
    ], delimiter="\t")


def write_report(
    path: Path,
    args: argparse.Namespace,
    motif_rows: List[Dict[str, object]],
    contacts: List[Dict[str, object]],
    summary: Dict[str, object],
    previous_rows: List[Tuple[str, int]],
) -> None:
    segs = segments(motif_rows)
    motif_residues = ["%s%d%s" % (row["chain"], int(row["residue"]), row["icode"]) for row in motif_rows]
    motif_sequence = "".join(str(row["aa"]) for row in motif_rows)
    previous_set = set(previous_rows)
    motif_set = {(str(row["chain"]), int(row["residue"])) for row in motif_rows}
    overlap = sorted(motif_set & previous_set, key=lambda item: (item[0], item[1]))
    only_current = sorted(motif_set - previous_set, key=lambda item: (item[0], item[1]))
    only_previous = sorted(previous_set - motif_set, key=lambda item: (item[0], item[1]))

    lines = [
        "# Motif Extraction Report",
        "",
        "## Inputs",
        "",
        "- complex: `%s`" % args.complex,
        "- antigen_chain: `%s`" % args.antigen_chain,
        "- antibody_heavy_chain: `%s`" % args.antibody_heavy_chain,
        "- antibody_light_chain: `%s`" % args.antibody_light_chain,
        "- heavy_atom_contact_cutoff_angstrom: `%.2f`" % args.cutoff,
        "- whitelist: `%s`" % (args.whitelist or ""),
        "- blacklist: `%s`" % (args.blacklist or ""),
        "",
        "## Epitope",
        "",
        "- residue_count: `%s`" % len(motif_rows),
        "- residue_list: `%s`" % ",".join(motif_residues),
        "- residue_sequence: `%s`" % motif_sequence,
        "- segmentation: `%s`" % ",".join("%d-%d" % item for item in segs),
        "- continuity: `%s`" % ("continuous" if len(segs) == 1 else "discontinuous"),
        "- heavy_chain_contact_count: `%s`" % summary["heavy_chain_contact_count"],
        "- light_chain_contact_count: `%s`" % summary["light_chain_contact_count"],
        "- total_atom_contact_count: `%s`" % len(contacts),
        "- buried_surface_proxy: heavy atom contact count and contacted antibody residue count only; true BSA not computed",
        "- warning: `%s`" % summary["warning"],
        "",
        "## Comparison With Previous Test Motif A163-181",
        "",
        "- overlap_residues: `%s`" % ",".join("%s%d" % item for item in overlap),
        "- current_only_residues: `%s`" % ",".join("%s%d" % item for item in only_current),
        "- previous_only_residues: `%s`" % ",".join("%s%d" % item for item in only_previous),
        "",
        "## Recommendation",
        "",
        summary["recommendation"],
        "",
        "## Contact Residues",
        "",
        "| residue | aa | min_distance | heavy_contacts | light_contacts | antibody_contact_residues |",
        "| --- | --- | ---: | ---: | ---: | --- |",
    ]
    for row in motif_rows:
        lines.append("| %s%d%s | %s | %s | %s | %s | %s |" % (
            row["chain"], int(row["residue"]), row["icode"], row["aa"],
            row["min_contact_distance_angstrom"], row["heavy_chain_contacts"],
            row["light_chain_contacts"], row["antibody_contact_residues"],
        ))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n")


def previous_test_rows() -> List[Tuple[str, int]]:
    return [("A", idx) for idx in range(163, 182)]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--complex", required=True, help="Input complex PDB or mmCIF.")
    parser.add_argument("--antigen_chain", required=True)
    parser.add_argument("--antibody_heavy_chain", required=True)
    parser.add_argument("--antibody_light_chain", required=True)
    parser.add_argument("--cutoff", type=float, default=4.5)
    parser.add_argument("--out_dir", default=".")
    parser.add_argument("--motif_tsv", default="")
    parser.add_argument("--contact_map_tsv", default="")
    parser.add_argument("--summary_csv", default="")
    parser.add_argument("--motif_reference_pdb", default="")
    parser.add_argument("--report_md", default="")
    parser.add_argument("--cleaned_pdb", default="")
    parser.add_argument("--chain_mapping_tsv", default="")
    parser.add_argument("--antigen_pdb", default="")
    parser.add_argument("--antibody_pdb", default="")
    parser.add_argument("--whitelist", default="")
    parser.add_argument("--blacklist", default="")
    args = parser.parse_args()

    out_dir = Path(args.out_dir)
    complex_path = Path(args.complex)
    atoms, header = read_structure(complex_path)
    if not atoms:
        raise SystemExit("No atoms parsed from %s" % complex_path)

    chain_set = {str(atom["chain"]) for atom in atoms if atom["record"] == "ATOM"}
    for chain in [args.antigen_chain, args.antibody_heavy_chain, args.antibody_light_chain]:
        if chain not in chain_set:
            raise SystemExit("Chain %s not found in %s; observed chains: %s" % (chain, complex_path, ",".join(sorted(chain_set))))

    residues = residue_order(atom for atom in atoms if atom["chain"] == args.antigen_chain and atom["record"] == "ATOM")
    whitelist = parse_residue_spec(args.whitelist)
    blacklist = parse_residue_spec(args.blacklist)
    contacts = contact_rows(atoms, args.antigen_chain, args.antibody_heavy_chain, args.antibody_light_chain, args.cutoff)
    motif_rows = summarize_residue_contacts(contacts, residues, whitelist, blacklist)
    segs = segments(motif_rows)
    warning = "none"
    if len(segs) > 3:
        warning = "motif_is_fragmented_more_than_3_segments"
    elif len(segs) > 1:
        warning = "motif_is_discontinuous"
    elif len(motif_rows) < 3:
        warning = "motif_has_fewer_than_3_contact_residues"
    recommendation = (
        "Use this contact-derived motif for benchmark only after comparing contact4/contact5 and RFdiffusion original A163-181 references. "
        "Prefer the smaller contact4 set when it captures the same key site-V residues; use contact5 if contact4 is too sparse."
    )
    if len(motif_rows) == 0:
        recommendation = "No contact epitope residues recovered at this cutoff; do not run scaffolding with this input."
    summary = OrderedDict([
        ("complex", str(complex_path)),
        ("antigen_chain", args.antigen_chain),
        ("antibody_heavy_chain", args.antibody_heavy_chain),
        ("antibody_light_chain", args.antibody_light_chain),
        ("cutoff_angstrom", "%.2f" % args.cutoff),
        ("motif_residue_count", len(motif_rows)),
        ("motif_sequence", "".join(str(row["aa"]) for row in motif_rows)),
        ("motif_segments", ";".join("%d-%d" % item for item in segs)),
        ("continuity", "continuous" if len(segs) == 1 else "discontinuous"),
        ("heavy_chain_contact_count", sum(int(row["heavy_chain_contacts"]) for row in motif_rows)),
        ("light_chain_contact_count", sum(int(row["light_chain_contacts"]) for row in motif_rows)),
        ("total_atom_contact_count", len(contacts)),
        ("contacted_antibody_residue_count", len({
            "%s%d%s" % (row["antibody_chain"], int(row["antibody_residue"]), str(row["antibody_icode"]))
            for row in contacts
        })),
        ("warning", warning),
        ("recommendation", recommendation),
    ])

    motif_tsv = Path(args.motif_tsv) if args.motif_tsv else out_dir / "motif_residues.tsv"
    contact_map = Path(args.contact_map_tsv) if args.contact_map_tsv else out_dir / "epitope_contact_map.tsv"
    summary_csv = Path(args.summary_csv) if args.summary_csv else out_dir / "antigen_antibody_interface_summary.csv"
    motif_pdb = Path(args.motif_reference_pdb) if args.motif_reference_pdb else out_dir / "motif_reference.pdb"
    report_md = Path(args.report_md) if args.report_md else out_dir / "motif_extraction_report.md"

    write_csv_rows(motif_tsv, motif_rows, [
        "chain", "residue", "icode", "resname", "aa", "motif_index",
        "min_contact_distance_angstrom", "heavy_chain_contacts", "light_chain_contacts",
        "total_atom_contacts", "antibody_contact_residues", "provenance",
    ], delimiter="\t")
    write_csv_rows(contact_map, contacts, [
        "cutoff_angstrom", "antigen_chain", "antigen_residue", "antigen_icode",
        "antigen_resname", "antigen_atom", "antibody_chain", "antibody_role",
        "antibody_residue", "antibody_icode", "antibody_resname", "antibody_atom",
        "distance_angstrom",
    ], delimiter="\t")
    write_summary(summary_csv, summary)
    motif_keys = {(str(row["chain"]), int(row["residue"]), str(row["icode"])) for row in motif_rows}
    write_pdb(motif_pdb, [atom for atom in atoms if residue_key(atom) in motif_keys and atom["record"] == "ATOM"])
    write_report(report_md, args, motif_rows, contacts, summary, previous_test_rows())

    if args.cleaned_pdb:
        selected_chains = {args.antigen_chain, args.antibody_heavy_chain, args.antibody_light_chain}
        write_pdb(Path(args.cleaned_pdb), [atom for atom in atoms if atom["record"] == "ATOM" and atom["chain"] in selected_chains])
    if args.antigen_pdb:
        write_pdb(Path(args.antigen_pdb), [atom for atom in atoms if atom["record"] == "ATOM" and atom["chain"] == args.antigen_chain])
    if args.antibody_pdb:
        antibody_chains = {args.antibody_heavy_chain, args.antibody_light_chain}
        write_pdb(Path(args.antibody_pdb), [atom for atom in atoms if atom["record"] == "ATOM" and atom["chain"] in antibody_chains])
    if args.chain_mapping_tsv:
        write_chain_mapping(Path(args.chain_mapping_tsv), atoms, header, args.antigen_chain, args.antibody_heavy_chain, args.antibody_light_chain)

    print("motif_residues=%d cutoff=%.2f output=%s" % (len(motif_rows), args.cutoff, motif_tsv))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
