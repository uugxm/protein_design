# RFD3 Contact-Motif Pilot Report

## Status

- Phase 2 production benchmark: not started.
- RFdiffusion v1 baseline: not expanded.
- c04 contact-core pilot status: `scaffold_or_contact_face_qc_limited`.
- c05 discontinuous/unindex status: `hold_not_cleanly_supported_in_current_wrapper`.

## Summary Table

| condition | validation | AF3 pass rate | RF3 confirmed | AF3 contact-face RMSD median | RF3 contact-face RMSD median | contact-face pass/caution/hold | interpretation |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| c03_a163_181_all_20_30 | legacy_or_reference | 0.7 | 5 | 2.14943 | 1.66391 | 0/25/0 | scaffold_or_contact_face_qc_limited |
| c04_contact_core_a169_178_all_20_30 | valid_ready_to_run | 0.45 | 5 | 3.16841 | 1.37023 | 0/25/0 | scaffold_or_contact_face_qc_limited |
| c05_discontinuous_contact_unindex_all | hold_not_cleanly_supported_in_current_wrapper |  | 0 |  |  | 0/0/0 | validation_hold_no_gpu_run |

## Answers

1. c04 A169-178 contact core cleanly scaffolded by RFD3: `scaffold_or_contact_face_qc_limited`.
2. c05 discontinuous contact set cleanly represented by current wrapper: `hold_not_cleanly_supported_in_current_wrapper`.
3. RFD3 advantage versus A163-181 continuous: compare c04 against c03; c03 remains `scaffold_or_contact_face_qc_limited`, c04 is `scaffold_or_contact_face_qc_limited`.
4. Contact-face QC can change ranking because it evaluates antibody-facing atom exposure, local occlusion, and contact-face RMSD separately from whole-motif RMSD.
5. Candidates for expression pre-QC should only be considered from rows with `contact_face_pass` plus AF3/RF3 confirmation; see `contact_face_qc.csv` before ordering.
6. RFdiffusion v1 remains the primary backend for continuous A163-181 motif reproduction.
7. RFD3 small production remains blocked unless c04/c05 shows clear contact-face benefit and reviewed candidate quality.
