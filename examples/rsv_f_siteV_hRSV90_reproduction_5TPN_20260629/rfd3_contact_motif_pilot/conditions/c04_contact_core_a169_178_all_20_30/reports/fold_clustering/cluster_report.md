# Fold Clustering Report

Input summary: `/public/home/yinyifan/protein_design/examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/conditions/c04_contact_core_a169_178_all_20_30/reports/consensus_summary.csv`
Predictor mode: `consensus`
Structure clustering backend: `python_ca_rmsd_fallback`

US-align/TM-align was not found, so global fold clustering used pairwise Kabsch C-alpha RMSD converted to an approximate similarity score. This fallback is useful for small local triage but is less stable than TM-score for topology-level clustering.

## Cluster Counts

- Designs retained after thresholds: 5
- Global fold clusters: 5
- Motif-local clusters: 5
- Sequence clusters: 5

## Shortlist

| rank | design | status | global | motif-local | sequence | recommended |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | design_18 | top5 | F2 | M2 | S2 | yes |
| 2 | design_17 | top5 | F1 | M1 | S1 | yes |
| 3 | design_19 | top5 | F3 | M3 | S3 | yes |
| 4 | design_2 | top5 | F4 | M4 | S4 | yes |
| 5 | design_6 | top5 | F5 | M5 | S5 | yes |

Boltz single-sequence disagreement, when present, is reported as a warning and is not used as a hard selection gate.

