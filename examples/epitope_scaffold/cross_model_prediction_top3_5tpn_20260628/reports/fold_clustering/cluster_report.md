# Fold Clustering Report

Input summary: `examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/consensus_summary.csv`
Predictor mode: `consensus`
Structure clustering backend: `python_ca_rmsd_fallback`

US-align/TM-align was not found, so global fold clustering used pairwise Kabsch C-alpha RMSD converted to an approximate similarity score. This fallback is useful for small local triage but is less stable than TM-score for topology-level clustering.

## Cluster Counts

- Designs retained after thresholds: 3
- Global fold clusters: 3
- Motif-local clusters: 3
- Sequence clusters: 3

## Shortlist

| rank | design | status | global | motif-local | sequence | recommended |
| ---: | --- | --- | --- | --- | --- | --- |
| 1 | design_1 | top5 | F1 | M1 | S1 | yes |
| 2 | design_9 | top5 | F3 | M3 | S3 | yes |
| 3 | design_4 | top5 | F2 | M2 | S2 | yes |

Boltz single-sequence disagreement, when present, is reported as a warning and is not used as a hard selection gate.

