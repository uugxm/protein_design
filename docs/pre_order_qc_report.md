# Pre-Order QC Policy

Pre-order QC is not a replacement for AF3/RF3 filtering. It is a final
pre-synthesis review that checks sequence integrity, expression risk, motif
retention, structural consistency, and candidate priority before any order sheet
is prepared.

Use:

```bash
python scripts/pre_order_qc.py --help
```

## Outputs

The script writes, in the chosen report directory:

- `pre_order_sequence_qc.csv`
- `pre_order_structure_qc.csv`
- `pre_order_qc_decision.csv`
- `cloning_ready_constructs.csv`

The cloning-ready table contains placeholders only. It does not add tags,
signal peptides, linkers, restriction sites, codon optimization, or expression
system assumptions.

## Decision Policy

- `pass`: AF3/RF3 consensus is strong, motif is intact, and no severe sequence
  liabilities are detected.
- `caution`: structure is acceptable but expression or sequence risk should be
  reviewed.
- `hold`: motif missing, severe sequence abnormality, high aggregation risk, or
  unresolved model inconsistency.

Boltz no-MSA disagreement is a warning unless the task has validated
MSA/template-enabled Boltz behavior.
