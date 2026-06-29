# RFD3 Contact-Motif Pilot Report

Date: 2026-06-29

Benchmark directory: `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/`

## Status

This pilot did not start a 100-200 backbone Phase 2 production benchmark and did not expand the RFdiffusion v1 baseline. It tested RFD3 only as a calibrated secondary backend for contact-core and discontinuous/contact-derived site V tasks.

The completed or validated conditions were:

- `c03_a163_181_all_20_30`: prior calibrated continuous RFD3 reference, A163-181, all motif heavy atoms, 20-30/motif/20-30.
- `c04_contact_core_a169_178_all_20_30`: new contact-core pilot, A169-178, all motif heavy atoms, 20-30/motif/20-30, 20 backbones.
- `c05_discontinuous_contact_unindex_all`: validation-only discontinuous contact-derived site V set using contact4 residues.

## Input Validation

| Condition | Validation status | GPU run | Motif | Selected atoms | Notes |
| --- | --- | --- | --- | ---: | --- |
| c04 | `valid_ready_to_run` | yes | A169-178 contact core | 69 | Continuous contact-core condition was cleanly represented. |
| c05 | `hold_not_cleanly_supported_in_current_wrapper` | no | contact4 discontinuous site V | 120 | Foundry syntax may be expressive enough, but the current normalization/TRB/fixed-position audit layer requires an exact concatenated motif sequence and cannot cleanly audit this discontinuous unindex case. |

c05 was intentionally stopped before GPU submission. No workaround or hacked discontinuous mapping was used.

## Results

| Condition | Raw motif RMSD median | AF3 PASS | AF3 motif RMSD median | RF3 confirmed | RF3 motif RMSD median | AF3 contact-face RMSD median | RF3 contact-face RMSD median | Contact-face pass/caution/hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| c03 A163-181 ALL 20-30 | 0.012541 | 14/20 | 1.73598 | 5/5 | 0.945571 | 2.14943 | 1.66391 | 0/25/0 |
| c04 A169-178 ALL 20-30 | 0.008618 | 9/20 | 2.55529 | 5/5 | 0.819113 | 3.16841 | 1.37023 | 0/25/0 |
| c05 discontinuous contact4 | not run | 0/0 | not run | 0/0 | not run | not run | not run | 0/0/0 |

c04 raw motif conditioning was excellent, with no evidence of a raw RFD3 motif placement failure. The downstream profile was weaker than the calibrated c03 continuous condition at the AF3 layer: c04 had lower AF3 pass rate, higher AF3 motif RMSD, and lower mean pLDDT. RF3 confirmed 5/5 selected c04 candidates and gave a lower median motif RMSD than c03, but contact-face QC still flagged every AF3 and RF3 model as caution rather than pass.

The main contact-face caution flags were low contact-face exposure proxy and possible local scaffold occlusion. This is the important practical result: good motif geometry, and even RF3 confirmation, did not by itself produce antibody-facing epitope surfaces that should be treated as expression-ready.

## Answers

1. c04 A169-178 contact core can be represented and scaffolded by RFD3, but the pilot result is contact-face limited. Raw motif RMSD was low, AF3 passed 9/20, and RF3 confirmed 5/5 selected candidates, yet contact-face QC produced 0 pass calls.

2. c05 discontinuous contact set cannot be cleanly represented by the current wrapper stack. The hold is not a claim that Foundry/RFD3 cannot support discontinuous motifs; it is a local normalization and audit limitation in the current workflow.

3. RFD3 did not show a clear advantage on contact-core/discontinuous site V in this pilot. c04 improved RF3 motif/contact-face RMSD relative to c03, but it lost AF3 pass rate and did not produce contact-face pass candidates.

4. Contact-face QC changed the interpretation. A simple motif RMSD/RF3 confirmation view would make c04 look promising, but exposure and occlusion proxies downgraded all candidates to caution.

5. No RFD3 candidates from this pilot should advance directly into expression pre-order QC. Candidate review could continue manually for method development, but the automated gate found no contact-face pass designs.

6. RFdiffusion v1 remains the primary backend for continuous A163-181 site V reproduction. RFD3 remains a calibrated secondary backend for atom-level, contact-core, complex, and discontinuous-motif exploration.

7. RFD3 should not enter small production yet for this benchmark. The next useful RFD3 work is wrapper-level support for auditable discontinuous/unindex mapping plus another small contact-face pilot, not a production expansion.

## Files

- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/reports/rfd3_contact_motif_input_validation.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/reports/rfd3_contact_motif_pilot_summary.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/conditions/c04_contact_core_a169_178_all_20_30/reports/contact_face_qc.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/conditions/c04_contact_core_a169_178_all_20_30/reports/all_filter_summary.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/conditions/c04_contact_core_a169_178_all_20_30/reports/rf3_filter_summary.csv`
