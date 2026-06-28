# Fold Clustering Report

Input summary: `examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/reports/all_filter_summary.csv`
Predictor mode: `af3`
Structure clustering backend: `python_ca_rmsd_fallback`

US-align/TM-align was not found, so global fold clustering used pairwise Kabsch C-alpha RMSD converted to an approximate similarity score. This fallback is useful for small local triage but is less stable than TM-score for topology-level clustering.

## Cluster Counts

- Designs retained after thresholds: 7
- Global fold clusters: 7
- Motif-local clusters: 7
- Sequence clusters: 6

## Shortlist

| rank | design | status | global | motif-local | sequence | recommended |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | design_1 | top5 | F2 | M2 | S2 | yes |
| 2 | design_0 | top5 | F1 | M1 | S1 | yes |
| 3 | design_7 | top5 | F6 | M6 | S6 | yes |
| 4 | design_2 | top5 | F3 | M3 | S3 | yes |
| 5 | design_3 | top5 | F4 | M4 | S4 | yes |
| 6 | design_9 | top10 | F7 | M7 | S3 | no |
| 7 | design_4 | top10 | F5 | M5 | S5 | no |

Boltz single-sequence disagreement, when present, is reported as a warning and is not used as a hard selection gate.

