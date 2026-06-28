# 5TPN Backend Comparison

This compact result bundle compares the stable RFdiffusion v1 backbone backend
against the experimental `rfdiffusion_all_atom_legacy` backend using the same downstream
ProteinMPNN, AF3, filter, merge, and ranking pipeline.

## Run

```text
Cluster run directory: /public/home/yinyifan/protein_design/examples/epitope_scaffold/backend_comparison_20260628_195056
Input PDB: 5TPN
Motif: chain A residues 163-181
RFdiffusion v1: 10 backbones
RFDiffusionAA: 10 backbones
ProteinMPNN: 4 sequences per backbone
AF3: top 1 sequence predicted per backbone in this speed test
```

The formal template supports top 1-2 AF3 predictions per backbone through
`PREDICT_MAX_RECORDS`.

## Slurm Jobs

```text
rfdiffusion_v1 backbone generation: 123186, COMPLETED, 00:04:34, gpu14
rfdiffusion_v1 ProteinMPNN array: 123187, 10/10 completed
rfdiffusion_v1 AF3 array: 123188, 9/10 first-pass completed
rfdiffusion_v1 failed AF3 task: 123188_5, retried as 123251_5, COMPLETED
rfdiffusion_v1 retry filter: 123252_5, COMPLETED
rfdiffusion_v1 retry merge: 123253, COMPLETED

rfdiffusion_all_atom_legacy backbone generation: 123191, COMPLETED, 00:21:28, gpu15
rfdiffusion_all_atom_legacy ProteinMPNN array: 123192, 10/10 completed
rfdiffusion_all_atom_legacy AF3 array: 123193, 9/10 first-pass completed
rfdiffusion_all_atom_legacy failed AF3 task: 123193_6, retried as 123254_6, COMPLETED
rfdiffusion_all_atom_legacy retry filter: 123255_6, COMPLETED
rfdiffusion_all_atom_legacy retry merge: 123256, COMPLETED

Final comparison refresh: 123258, COMPLETED, computer1
```

## Final Summary

| backend | backbone success | MPNN success | AF3 success | filter PASS | pLDDT mean | PAE mean | motif RMSD mean | clash mean | top design | top PASS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfdiffusion_v1 | 10/10 | 10/10 | 10/10 | 9/10 | 83.6895 | 4.3982 | 1.2157 | 0.1000 | design_3 | PASS |
| rfdiffusion_all_atom_legacy | 10/10 | 10/10 | 10/10 | 0/10 | 88.8509 | 7.0484 | 6.5673 | 0.0000 | design_8 | FAIL |

The all-atom backend was technically compatible with the shared pipeline, but in
this 5TPN ligand-free motif test its predicted motif placement failed the motif
RMSD threshold for all 10 designs. Keep RFdiffusion v1 as the stable baseline.

## Files

```text
reports/backend_comparison.csv
reports/backend_comparison.md
rfdiffusion_v1/reports/all_filter_summary.csv
rfdiffusion_v1/reports/top_designs.csv
rfdiffusion_v1/reports/run_report.json
rfdiffusion_all_atom_legacy/reports/all_filter_summary.csv
rfdiffusion_all_atom_legacy/reports/top_designs.csv
rfdiffusion_all_atom_legacy/reports/run_report.json
job_ids.env
rfdiffusion_v1/job_ids.env
rfdiffusion_all_atom_legacy/job_ids.env
logs/
```
