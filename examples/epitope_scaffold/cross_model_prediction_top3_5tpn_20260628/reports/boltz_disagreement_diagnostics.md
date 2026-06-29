# Boltz Motif Disagreement Diagnostics

AF3 is the primary prediction backend, RF3 is optional confirmation, and Boltz is an optional conflict flag until MSA/template-enabled validation is tested.

Boltz was run in no-MSA single-sequence mode for these diagnostics.

| design | motif atoms compared | motif atoms missing | motif RMSD | median all-chain CA-CA | median motif CA-CA | source structure |
| --- | ---: | ---: | ---: | ---: | ---: | --- |
| design_1 | 76 | 0 | 552.226 | 735.034 | 750.659 | `predictions_boltz/boltz_results_boltz/predictions/design_1_T_0.1_sample_1_score_1.0821_global_score_1.2770_seq_recovery_0.0847.boltz/design_1_T_0.1_sample_1_score_1.0821_global_score_1.2770_seq_recovery_0.0847.boltz_model_0.cif` |
| design_9 | 76 | 0 | 549.851 | 691.462 | 679.789 | `predictions_boltz/boltz_results_boltz/predictions/design_9_T_0.1_sample_4_score_1.1683_global_score_1.4381_seq_recovery_0.0250.boltz/design_9_T_0.1_sample_4_score_1.1683_global_score_1.4381_seq_recovery_0.0250.boltz_model_0.cif` |

Interpretation:

- The motif sequence mapping is present for the sampled Boltz outputs: design_1 and design_9 both compare 76 backbone motif atoms with 0 missing atoms.
- The collector selected the expected Boltz model CIFs listed in `predictions_flat/boltz/cross_model_top3.prediction_manifest.json`.
- The original Boltz CIF coordinates already have hundreds-of-Angstrom coordinate ranges, so the disagreement is not introduced by CIF-to-PDB conversion.
- Consecutive CA distances are hundreds of Angstroms, including inside the mapped motif. This is consistent with a severe no-MSA Boltz structural failure for this task, not with a small residue-numbering offset.
- Conclusion: Boltz no-MSA mode is not reliable as a hard gate for this de novo motif scaffold task. Treat it as an optional conflict flag until MSA/template-enabled validation is tested.

Artifacts:

- `design_1` mapping TSV: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_1_boltz_motif_mapping.tsv`
- `design_1` aligned motif PDB: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_1_boltz_motif_aligned.pdb`
- `design_1` PyMOL script: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_1_boltz_motif_alignment.pml`
- `design_9` mapping TSV: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_9_boltz_motif_mapping.tsv`
- `design_9` aligned motif PDB: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_9_boltz_motif_aligned.pdb`
- `design_9` PyMOL script: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/boltz_motif_diagnostics/design_9_boltz_motif_alignment.pml`
