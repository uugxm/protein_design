# Final Candidate Selection Report

Date: 2026-06-29

This report closes the current 5TPN epitope scaffold computational selection pass. The stable evidence chain is:

```text
RFdiffusion v1 backbone -> ProteinMPNN fixed-position design -> AF3 primary prediction -> RF3 confirmation -> motif/clash filtering -> fold diversity shortlist -> expression package
```

No changes were made to the working RFdiffusion v1, ProteinMPNN, AF3, RF3, or Boltz pipelines. This step only packages candidates, validates AF3-only backups with RF3, and records the final expression recommendation.

## Evidence Policy

AF3/RF3 consensus is the primary computational evidence. A design is promoted when AF3 passes the primary filter and RF3 independently confirms the fold with acceptable motif RMSD, confidence, PAE, and clash count.

Boltz no-MSA single-sequence predictions are not used as a hard filter for this task. Prior diagnostics showed very large Boltz motif RMSD for otherwise AF3/RF3-consistent de novo motif scaffolds, consistent with the current no-MSA mode being unreliable for this specific scaffold-validation use case. Boltz is therefore retained only as a warning signal until MSA/template-enabled Boltz inputs are tested.

Fold clustering is used after AF3/RF3 filtering to avoid over-selecting repeated scaffold topologies. The selection considers global fold cluster, motif-local geometry cluster, and sequence cluster. Motif-local clustering is weighted most heavily because epitope display depends on the support geometry around the grafted motif, not only on the whole-scaffold topology.

## Primary Expression Package

Output directory:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/
```

Primary candidate subdirectories:

- `design_1/`
- `design_9/`
- `design_4/`

Each primary candidate package contains:

- final designed amino-acid sequence FASTA
- AF3 model PDB and generated mmCIF
- RF3 model PDB and mmCIF
- RFdiffusion backbone PDB
- RFdiffusion/RF3 mapping TRB files
- motif mapping TSV
- motif-only aligned PDB
- PyMOL motif QC script
- per-design QC JSON
- per-design summary Markdown

Visualization scripts:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_1_motif_qc.pml
examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_9_motif_qc.pml
examples/epitope_scaffold/final_candidates_5tpn_20260629/visualization/design_4_motif_qc.pml
```

The PyMOL scripts load the reference-aligned motif, AF3 model, RF3 model, and RFdiffusion backbone; highlight reference/AF3/RF3 motif atoms; and select local support residues within 8 Angstrom of the motif.

## Final Expression Shortlist

Final table:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/final_expression_shortlist.csv
```

| rank | design | tier | priority | AF3 motif RMSD | RF3 motif RMSD | rationale |
| ---: | --- | --- | --- | ---: | ---: | --- |
| 1 | design_1 | primary | high | 0.721 | 0.751 | Best combined AF3/RF3 motif preservation; distinct cluster F1/M1/S1. |
| 2 | design_9 | primary | high | 1.042 | 1.050 | Strong AF3/RF3 confidence; distinct cluster F3/M3/S3 from design_1. |
| 3 | design_4 | primary | medium | 1.850 | 1.680 | RF3-confirmed but weaker RF3 confidence and higher motif RMSD than design_1/design_9. |
| 4 | design_0 | backup | medium | 0.830 | 0.788 | RF3 backup validation passed; same F1/M1/S1 cluster family as design_1, so lower diversity priority. |
| 5 | design_7 | backup | medium | 0.891 | 0.904 | RF3 backup validation passed; distinct F6/M6/S6 cluster. |
| 6 | design_2 | backup | medium | 0.953 | 1.021 | RF3 backup validation passed; same F3/M3/S3 cluster family as design_9. |
| 7 | design_3 | backup | medium | 1.039 | 0.862 | RF3 backup validation passed; distinct F4/M4/S4 cluster. |

Recommended ordering:

1. Express `design_1` and `design_9` first.
2. Include `design_4` if capacity allows a third primary consensus candidate.
3. Use `design_7` and `design_3` as the most diverse backup expansion candidates.
4. Use `design_0` and `design_2` as cluster-family backups for `design_1` and `design_9`, respectively.

## RF3 Backup Validation

Output directory:

```text
examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/
```

Slurm job:

- job ID: `123402`
- node: `gpu14`
- state: `COMPLETED`
- elapsed: `00:01:35`

Validated AF3-only diverse backup candidates:

| design | AF3 pass | RF3 pass | RF3 motif RMSD | decision |
| --- | --- | --- | ---: | --- |
| design_0 | PASS | PASS | 0.788 | upgrade to backup consensus |
| design_7 | PASS | PASS | 0.904 | upgrade to backup consensus |
| design_2 | PASS | PASS | 1.021 | upgrade to backup consensus |
| design_3 | PASS | PASS | 0.862 | upgrade to backup consensus |

Generated reports:

```text
examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/reports/rf3_filter_summary.csv
examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/reports/updated_consensus_summary.csv
examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/reports/updated_top_consensus_designs.csv
examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/reports/run_report.json
```

## Experimental Next Steps

Recommended wet-lab path:

1. Small-scale expression for `design_1` and `design_9`, with `design_4` included if the expression panel can support three primary constructs.
2. Add `design_7` and `design_3` if expanding the first pass to five constructs; they provide additional fold/motif-local diversity.
3. Run SEC to check monodispersity and aggregation.
4. Run DSF or comparable thermal-shift assay for folded stability.
5. Test motif display by motif-specific antibody binding or direct target-binding assay, depending on the biological readout available.
6. Keep `design_0` and `design_2` as same-family backups for `design_1` and `design_9` rather than top diversity picks.

If Boltz is revisited, use canonical inputs with MSA/template assets and rerun the cross-model diagnostic before promoting Boltz to a hard filter.
