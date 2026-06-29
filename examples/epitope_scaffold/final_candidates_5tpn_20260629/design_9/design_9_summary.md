# design_9 Final Candidate Summary

- design_id: `design_9`
- source backend: RFdiffusion v1
- recommended experimental priority: `high`
- selection reason: AF3/RF3 PASS; diversity-aware representative; motif_rmsd_lt_1.5
- global fold cluster: `F3`
- motif-local cluster: `M3`
- sequence cluster: `S3`

## ProteinMPNN

- score: `1.2197`
- global_score: `1.4728`
- seq_recovery: `0.0250`

## Prediction QC

| predictor | pass | pLDDT | PAE | motif RMSD | clash_count |
| --- | --- | ---: | ---: | ---: | ---: |
| AF3 | PASS | 91.4301 | 2.6374 | 1.04193 | 0 |
| RF3 | PASS | 89.6143 | 1.37633 | 1.04981 | 0 |

## Boltz Warning

BOLTZ_SINGLE_SEQUENCE_DISAGREEMENT:low_plddt;high_motif_rmsd

## Files

- sequence_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_final_sequence.fasta`
- canonical_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_canonical_input.json`
- canonical_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_canonical_backbone.cif`
- af3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_af3_model.pdb`
- af3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_af3_model.cif`
- af3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_af3_confidence.json`
- rf3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rf3_model.pdb`
- rf3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rf3_model.cif`
- rf3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rf3_confidence.json`
- backbone_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rfdiffusion_backbone.pdb`
- backbone_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rfdiffusion_mapping.trb`
- rf3_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_rf3_mapping.trb`
- mpnn_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_proteinmpnn_all_sequences.fa`
- motif_only_aligned_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_motif_only_aligned.pdb`
- motif_mapping_tsv: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_9/design_9_motif_mapping.tsv`
- pymol_script: `examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_9_motif_qc.pml`
