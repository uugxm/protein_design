# Cross-Model Prediction Summary

| predictor | success | pass | failed | missing |
| --- | ---: | ---: | ---: | ---: |
| af3 | 3 | 3 | 0 | 0 |
| rf3 | 3 | 3 | 0 | 0 |
| boltz | 3 | 0 | 0 | 0 |

- RF3 successful predictions: 3
- Boltz successful predictions: 3
- AF3/RF3/Boltz motif RMSD all pass: 0
- AF3/RF3 recommended designs: design_1, design_9, design_4
- AF3-only positives to downgrade: none
- Model-conflict designs: design_1, design_4, design_9

Top design recommendation uses AF3+RF3 consensus as the main decision layer.
Boltz single-sequence disagreement is recorded as a warning, not as a hard
filter. See `top_consensus_designs.csv`.

| rank | design | recommendation | Boltz warning |
| ---: | --- | --- | --- |
| 1 | design_1 | RECOMMENDED | low pLDDT; high motif RMSD |
| 2 | design_9 | RECOMMENDED | low pLDDT; high motif RMSD |
| 3 | design_4 | RECOMMENDED | low pLDDT; high motif RMSD; one missing motif atom |

Boltz disagreement diagnostics for design_1 and design_9 are in
`boltz_disagreement_diagnostics.md` and `boltz_motif_diagnostics/`. Both sampled
Boltz outputs have complete motif mappings and expected collector source CIFs,
but the original Boltz CIF coordinates and consecutive CA distances are
hundreds of Angstroms. This supports a true no-MSA Boltz prediction failure for
this task, not a mapping or collector error.

Final interpretation: AF3 primary, RF3 optional confirmation, Boltz optional
conflict flag until MSA/template-enabled validation is tested.
