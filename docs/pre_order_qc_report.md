# Pre-order QC Report

Date: 2026-06-29

This pre-order QC step is not a replacement for AF3/RF3 filtering. Its purpose is to check sequence integrity, expression-risk flags, motif retention, structure consistency, and candidate priority before any gene synthesis or cloning-ready order sheet is created.

Inputs:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/final_expression_shortlist.csv
```

Primary candidates:

- `design_1`
- `design_9`
- `design_4`

Backup candidates:

- `design_7`
- `design_3`
- `design_0`
- `design_2`

Generated reports:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_sequence_qc.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_structure_qc.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_qc_decision.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/cloning_ready_constructs.csv
```

## Sequence QC

All seven candidates contain the intact motif sequence:

```text
EVNKIKSALLSTNKAVVSL
```

No noncanonical amino acids were detected. No severe long hydrophobic stretch or low-complexity repeat was flagged by the current protein-level screen.

Potential sequence cautions:

- `design_4`: one NXS/T motif, `NLT24-26`
- `design_7`: three NXS/T motifs, `NGT9-11`, `NYT44-46`, `NAT66-68`
- `design_3`: one NXS/T motif, `NLS26-28`

These are expression-system-dependent cautions, not automatic failures. They matter most if a eukaryotic secretory expression system is later chosen.

Closest sequence redundancy observed:

- `design_9` and `design_2`: 39.3% identity by the current simple pairwise identity metric.
- No candidate exceeded the 90% high-redundancy threshold.

## Structure QC

All seven candidates remain AF3/RF3 consensus-positive:

| design | AF3 motif RMSD | RF3 motif RMSD | AF3 pLDDT | RF3 pLDDT | decision |
| --- | ---: | ---: | ---: | ---: | --- |
| design_1 | 0.721 | 0.751 | 90.439 | 86.327 | acceptable caution |
| design_9 | 1.042 | 1.050 | 91.430 | 89.614 | acceptable caution |
| design_4 | 1.850 | 1.680 | 87.227 | 73.972 | acceptable caution |
| design_0 | 0.830 | 0.788 | 79.340 | 77.256 | acceptable caution |
| design_7 | 0.891 | 0.904 | 84.718 | 83.930 | acceptable caution |
| design_2 | 0.953 | 1.021 | 83.296 | 86.157 | acceptable caution |
| design_3 | 1.039 | 0.862 | 85.363 | 81.622 | acceptable caution |

Motif atoms:

- `motif_atoms_missing = 0` for all candidates.
- AF3 clash count is 0 for all except `design_3`, which has 1 clash by the current 2.0 Angstrom heavy-atom cutoff and remains below threshold.

Motif solvent exposure:

- A simple Shrake-Rupley-like heavy-atom proxy was computed from AF3 models using a 1.4 Angstrom probe.
- Accessible motif area is nonzero for all candidates, but accessible fraction is low by this proxy, so all designs receive a caution flag.
- This flag should be interpreted as a pre-order visualization/QC prompt, not as a hard failure. The PyMOL motif QC scripts should be reviewed before ordering.

Boltz:

- `design_1`, `design_9`, and `design_4` retain the previous Boltz no-MSA warning.
- Boltz no-MSA is not used as a hard gate because prior diagnostics showed it is unreliable for this de novo 5TPN motif scaffold task without MSA/template assets.

## Decision Table

Current QC decisions:

| design | tier | QC status | order_now | main risks |
| --- | --- | --- | --- | --- |
| design_1 | primary | caution | yes | low motif exposure proxy; Boltz no-MSA warning |
| design_9 | primary | caution | yes | low motif exposure proxy; Boltz no-MSA warning |
| design_4 | primary | caution | yes | NXS/T motif; low motif exposure proxy; Boltz no-MSA warning |
| design_0 | backup | caution | yes | low motif exposure proxy |
| design_7 | backup | caution | yes | NXS/T motifs; low motif exposure proxy |
| design_2 | backup | caution | yes | low motif exposure proxy |
| design_3 | backup | caution | yes | NXS/T motif; low motif exposure proxy |

No candidate is on hold. The caution status means the design can proceed into a placeholder cloning-ready construct table, but expression system, vector, tags, signal peptide, linker, restriction sites, and codon optimization must remain unspecified until the user chooses them.

## Cloning-ready Placeholder Table

The generated `cloning_ready_constructs.csv` includes only candidates with `order_now=yes`. It intentionally does not add:

- affinity tags
- signal peptides
- linkers
- restriction sites
- codon optimization

Those fields are placeholders only and must be filled after the expression system and vector are specified.

Recommended pre-order priority remains:

1. `design_1`
2. `design_9`
3. `design_4`
4. `design_7`
5. `design_3`
6. `design_0`
7. `design_2`

Before generating a true order sheet, review the PyMOL motif QC views for motif exposure, then choose expression system and vector constraints.
