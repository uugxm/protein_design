# design_4 Final Candidate Summary

- design_id: `design_4`
- source backend: RFdiffusion v1
- recommended experimental priority: `medium`
- selection reason: AF3/RF3 PASS; diversity-aware representative; motif_rmsd_threshold_pass
- global fold cluster: `F2`
- motif-local cluster: `M2`
- sequence cluster: `S2`

## ProteinMPNN

- score: `1.1247`
- global_score: `1.4583`
- seq_recovery: `0.0244`

## Prediction QC

| predictor | pass | pLDDT | PAE | motif RMSD | clash_count |
| --- | --- | ---: | ---: | ---: | ---: |
| AF3 | PASS | 87.2266 | 3.35261 | 1.84953 | 0 |
| RF3 | PASS | 73.9715 | 7.40633 | 1.67975 | 0 |

## Boltz Warning

BOLTZ_SINGLE_SEQUENCE_DISAGREEMENT:low_plddt;high_motif_rmsd;motif_atoms_missing

## Files

- sequence_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_final_sequence.fasta`
- canonical_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_canonical_input.json`
- canonical_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_canonical_backbone.cif`
- af3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_af3_model.pdb`
- af3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_af3_model.cif`
- af3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_af3_confidence.json`
- rf3_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rf3_model.pdb`
- rf3_cif: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rf3_model.cif`
- rf3_json: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rf3_confidence.json`
- backbone_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rfdiffusion_backbone.pdb`
- backbone_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rfdiffusion_mapping.trb`
- rf3_trb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_rf3_mapping.trb`
- mpnn_fasta: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_proteinmpnn_all_sequences.fa`
- motif_only_aligned_pdb: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_motif_only_aligned.pdb`
- motif_mapping_tsv: `examples/epitope_scaffold/final_candidates_5tpn_20260629/design_4/design_4_motif_mapping.tsv`
- pymol_script: `examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_4_motif_qc.pml`
