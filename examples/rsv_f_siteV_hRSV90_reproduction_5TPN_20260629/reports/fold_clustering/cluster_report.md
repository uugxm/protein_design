# Fold Clustering Report

Input summary: `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/reports/all_filter_summary.csv`
Predictor mode: `af3`
Structure clustering backend: `python_ca_rmsd_fallback`

US-align/TM-align was not found, so global fold clustering used pairwise Kabsch C-alpha RMSD converted to an approximate similarity score. This fallback is useful for small local triage but is less stable than TM-score for topology-level clustering.

## Cluster Counts

- Designs retained after thresholds: 26
- Global fold clusters: 23
- Motif-local clusters: 26
- Sequence clusters: 26

## Shortlist

| rank | design | status | global | motif-local | sequence | recommended |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | rfdiffusion_v1__design_15 | top5 | F14 | M15 | S15 | yes |
| 2 | rfdiffusion_v1__design_14 | top5 | F13 | M14 | S14 | yes |
| 3 | rfdiffusion_v1__design_3 | top5 | F20 | M21 | S21 | yes |
| 4 | rfdiffusion_v1__design_9 | top5 | F23 | M26 | S26 | yes |
| 5 | rfdiffusion_v1__design_16 | top5 | F15 | M16 | S16 | yes |
| 6 | foundry_rfd3__design_0 | top10 | F1 | M1 | S1 | no |
| 7 | rfdiffusion_v1__design_7 | top10 | F22 | M25 | S25 | no |
| 8 | rfdiffusion_v1__design_18 | top10 | F17 | M18 | S18 | no |
| 9 | rfdiffusion_v1__design_12 | top10 | F12 | M12 | S12 | no |
| 10 | foundry_rfd3__design_4 | top10 | F5 | M5 | S5 | no |

Boltz single-sequence disagreement, when present, is reported as a warning and is not used as a hard selection gate.

