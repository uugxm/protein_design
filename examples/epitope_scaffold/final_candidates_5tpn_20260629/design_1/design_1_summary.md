# design_1 Final Candidate Summary

- design_id: `design_1`
- source backend: RFdiffusion v1
- recommended experimental priority: `high`
- selection reason: AF3/RF3 PASS; diversity-aware representative; motif_rmsd_lt_1.5
- global fold cluster: `F1`
- motif-local cluster: `M1`
- sequence cluster: `S1`

## ProteinMPNN

- score: `1.0821`
- global_score: `1.2770`
- seq_recovery: `0.0847`

## Prediction QC

| predictor | pass | pLDDT | PAE | motif RMSD | clash_count |
| --- | --- | ---: | ---: | ---: | ---: |
| AF3 | PASS | 90.439 | 2.72235 | 0.721181 | 0 |
| RF3 | PASS | 86.3269 | 1.72056 | 0.750603 | 1 |

## Boltz Warning

BOLTZ_SINGLE_SEQUENCE_DISAGREEMENT:low_plddt;high_motif_rmsd

## Files

- sequence_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_final_sequence.fasta`
- canonical_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_canonical_input.json`
- canonical_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_canonical_backbone.cif`
- af3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_af3_model.pdb`
- af3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_af3_model.cif`
- af3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_af3_confidence.json`
- rf3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rf3_model.pdb`
- rf3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rf3_model.cif`
- rf3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rf3_confidence.json`
- backbone_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rfdiffusion_backbone.pdb`
- backbone_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rfdiffusion_mapping.trb`
- rf3_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_rf3_mapping.trb`
- mpnn_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_proteinmpnn_all_sequences.fa`
- motif_only_aligned_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_motif_only_aligned.pdb`
- motif_mapping_tsv: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_1/design_1_motif_mapping.tsv`
- pymol_script: `examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_1_motif_qc.pml`
