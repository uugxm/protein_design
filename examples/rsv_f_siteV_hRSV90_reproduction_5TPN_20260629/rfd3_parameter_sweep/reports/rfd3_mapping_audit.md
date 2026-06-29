# RFD3 Mapping Audit

Motif audited: `A163-181`.

This audit follows selected Foundry RFD3 Phase 1 designs from raw Foundry output through normalization, TRB mapping, ProteinMPNN fixed positions, canonical predictor inputs, AF3 output, and RF3 confirmation when present.

## Summary

- Designs audited: 6
- Mapping PASS: 6
- Mapping FAIL: 0

| group | design | AF3 pass | mapped residues | fixed positions | MPNN motif | AF3 input | AF3 model | RF3 model | overall |
| --- | --- | --- | ---: | --- | --- | --- | --- | --- | --- |
| PASS | design_0 | PASS | 19/19 | ok | ok | ok | ok | ok | PASS |
| PASS | design_4 | PASS | 19/19 | ok | ok | ok | ok | ok | PASS |
| PASS | design_6 | PASS | 19/19 | ok | ok | ok | ok | ok | PASS |
| FAIL | design_1 | FAIL | 19/19 | ok | ok | ok | ok | not_run_or_missing | PASS |
| FAIL | design_2 | FAIL | 19/19 | ok | ok | ok | ok | not_run_or_missing | PASS |
| FAIL | design_3 | FAIL | 19/19 | ok | ok | ok | ok | not_run_or_missing | PASS |

## Interpretation Rule

- If normalized PDB/TRB/fixed positions/FASTA/AF3 input all preserve the motif but AF3/RF3 motif RMSD degrades, the likely failure layer is downstream scaffold stability or predictor response, not RFD3 motif mapping.
- If any fixed-position or sequence-preservation field is `mismatch`, the RFD3 result is not interpretable until normalization and fixed-position mapping are corrected.
