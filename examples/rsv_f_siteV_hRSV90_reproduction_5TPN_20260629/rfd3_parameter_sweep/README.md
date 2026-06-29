# RFD3 Parameter Sweep

This directory calibrates Foundry RFD3 on the RSV F site V/hRSV90 benchmark before any Phase 2 production benchmark is considered.

The first pass intentionally runs only three 20-backbone continuous-motif RFD3 conditions:

- `rfd3_c01_a163_181_bkbn_10_40`
- `rfd3_c02_a163_181_all_10_40`
- `rfd3_c03_a163_181_all_20_30`

The core and contact-derived discontinuous conditions are recorded in `condition_manifest.tsv` but are not default-submitted until the raw motif and mapping audits are interpretable.

Run from the cluster runtime directory:

```bash
bash examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_parameter_sweep/run_rfd3_parameter_sweep.sh
```

The script submits Slurm jobs only; it does not run design compute on the login node.
