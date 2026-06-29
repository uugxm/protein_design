# 5TPN Three-Way Backbone Backend Comparison

Date: 2026-06-28

Purpose: compare the stable RFdiffusion v1 backend, the legacy Baker
RFDiffusionAA backend, and the experimental Foundry RFD3 backend on the same
5TPN epitope scaffold task.

```text
Motif: 5TPN chain A residues 163-181
Backends: rfdiffusion_v1, rfdiffusion_all_atom_legacy, foundry_rfd3
Backbones per backend: 10
ProteinMPNN sequences per backbone: 4
AF3 predictions per backbone: top 1 sequence
Foundry RFD3 timesteps: 50
Foundry RFD3 batch size: 2
```

Final summary after targeted AF3 retries:

| backend | backbone success | ProteinMPNN success | AF3 success | filter PASS rate | mean pLDDT | mean PAE | mean motif RMSD | mean clash_count |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| rfdiffusion_v1 | 1.00 | 1.00 | 1.00 | 0.90 | 83.11 | 4.81 | 1.93 | 0.10 |
| rfdiffusion_all_atom_legacy | 1.00 | 1.00 | 1.00 | 0.00 | 88.85 | 7.05 | 6.57 | 0.00 |
| foundry_rfd3 | 1.00 | 1.00 | 1.00 | 0.40 | 78.89 | 6.13 | 3.12 | 0.00 |

Important outputs:

```text
reports/backend_comparison.csv
reports/backend_comparison.md
reports/run_report.json
<backend>/reports/all_filter_summary.csv
<backend>/reports/top_designs.csv
<backend>/run_params.json
<backend>/job_ids.env
<backend>/logs/
```

Retry notes are recorded in `reports/run_report.json`. RFdiffusion v1 remains
the stable baseline; Foundry RFD3 should be treated as an experimental backend.
