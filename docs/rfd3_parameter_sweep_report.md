# RFD3 Parameter Sweep Report

Benchmark directory: `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_parameter_sweep/`

## Status

RFD3 parameter calibration is complete for the first three 20-backbone conditions. No 100-200 backbone Phase 2 production benchmark was started, and the RFdiffusion v1 baseline was not expanded.

The updated RFD3 usage strategy is recorded in `docs/rfd3_paper_usage_review.md`: Foundry RFD3 should not be treated as a simple RFdiffusion v1 contig replacement, and RFD3 Phase 2 production should wait until contact-core and discontinuous/contact-derived pilots are reviewed.

The completed conditions were:

- `rfd3_c01_a163_181_bkbn_10_40`: A163-181, backbone atoms fixed, 10-40/motif/10-40.
- `rfd3_c02_a163_181_all_10_40`: A163-181, all motif heavy atoms fixed, 10-40/motif/10-40.
- `rfd3_c03_a163_181_all_20_30`: A163-181, all motif heavy atoms fixed, 20-30/motif/20-30.

The core A169-178 and contact-derived discontinuous conditions remain documented in `condition_manifest.tsv` but were not run in this pass.

## Raw Motif Audit

The raw backbone audit does not support a primary RFD3 motif-conditioning failure.

| Backend / condition | raw motif RMSD median | motif atoms missing |
|---|---:|---:|
| Phase 1 RFdiffusion v1 | 0.302805 | 0 |
| Phase 1 Foundry RFD3 | 0.011010 | 0 |
| RFD3 c01 BKBN 10-40 | 0.011010 | 0 |
| RFD3 c02 ALL 10-40 | 0.012541 | 0 |
| RFD3 c03 ALL 20-30 | 0.012541 | 0 |

RFD3 preserved the fixed motif geometry extremely tightly at the raw backbone layer in all audited settings.

## Mapping Audit

The RFD3 mapping audit sampled 3 Phase 1 AF3 PASS and 3 AF3 FAIL designs. All 6 passed mapping checks:

- 19/19 A163-181 motif residues mapped.
- Residue order and chain were correct.
- ProteinMPNN fixed positions matched the mapped motif positions.
- Motif sequence was preserved in designed FASTA and AF3 input.
- AF3 models preserved the motif sequence.
- RF3 model sequence was confirmed where RF3 had been run.

This argues against RFD3-to-PDB/TRB normalization, fixed-position JSON, or canonical predictor input construction as the primary cause of the weak Phase 1 RFD3 result.

## Parameter Sweep Results

| Condition | AF3 PASS | AF3 pass rate | AF3 motif RMSD median | RF3 confirmed | RF3 motif RMSD median | mean pLDDT | mean PAE | fold clusters |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| c01 BKBN 10-40 | 5/20 | 0.25 | 2.44110 | 4/5 | 2.11287 | 71.0505 | 10.3607 | 4 |
| c02 ALL 10-40 | 9/20 | 0.45 | 3.85149 | 5/5 | 0.953701 | 77.2864 | 8.0285 | 5 |
| c03 ALL 20-30 | 14/20 | 0.70 | 1.73598 | 5/5 | 0.945571 | 81.8621 | 5.73862 | 5 |

Best RFD3 setting in this sweep: `A163-181 + all-heavy-fixed + 20-30/motif/20-30`.

Top c03 candidates from diversity selection were `design_13`, `design_11`, `design_0`, `design_4`, and `design_18`. These are calibration candidates only; they are not cloning-ready constructs.

## Answers

1. Is current RFD3 weakness caused by raw motif conditioning?

No. Raw RFD3 motif RMSD was near-zero with no missing motif atoms. The weak Phase 1 result appears after sequence design and structure prediction.

2. Is it caused by RFD3-to-PDB/TRB normalization or fixed-position mapping?

No evidence for that. The mapping audit passed for both AF3 PASS and AF3 FAIL designs.

3. Is it caused by ProteinMPNN rewriting or not respecting the motif?

No evidence for motif rewrite. The fixed motif sequence was preserved in ProteinMPNN FASTA and AF3 input for audited designs.

4. Is it caused by AF3/RF3 instability on RFD3 scaffolds?

Partly yes. The raw motif is intact, but AF3 pass rate and AF3 motif RMSD vary strongly with RFD3 fixed atom level and length bin. This points to scaffold context and downstream foldability/predictor stability rather than motif placement alone.

5. Which RFD3 parameter combination was best?

`A163-181 + all-heavy-fixed + 20-30/motif/20-30`. It improved AF3 pass rate to 14/20 and RF3 confirmation to 5/5, with RF3 median motif RMSD 0.945571.

6. Is RFD3 worth entering Phase 2 production benchmark?

Not as an immediate replacement for RFdiffusion v1 on this continuous A163-181 motif. The calibrated best RFD3 condition is substantially better than the initial RFD3 setting, but it still does not clearly exceed the Phase 1 v1 result, which had 19/20 AF3 pass and lower RF3 median motif RMSD.

Recommended next step is not a 100-200 backbone production run. If RFD3 is pursued, run one more small validation focused on `all-heavy + 20-30` and the contact-core/discontinuous motif cases before allocating Phase 2 production resources.

7. If still weaker than v1, should RFD3 be positioned differently?

Yes. For this benchmark, RFD3 should be treated as a calibrated secondary backend for all-atom, complex, contact-core, or discontinuous motif exploration, not as the default replacement for RFdiffusion v1 continuous motif scaffolding.

## Files

- `reports/raw_backbone_motif_audit.csv`
- `reports/rfd3_mapping_audit.csv`
- `reports/rfd3_mapping_audit.md`
- `reports/rfd3_parameter_sweep_summary.csv`
- `conditions/*/reports/raw_backbone_motif_audit.csv`
- `conditions/*/reports/all_filter_summary.csv`
- `conditions/*/reports/rf3_filter_summary.csv`
- `conditions/*/reports/fold_clustering/diverse_shortlist.csv`
