# RFD3 Contact-Motif Pilot

This pilot tests Foundry RFD3 on hRSV90 contact-face motif definitions rather than treating RFD3 as an RFdiffusion v1 contig replacement.

Conditions:

- `c04_contact_core_a169_178_all_20_30`: continuous A169-178 contact core, `ALL` motif heavy atoms, `20-30/motif/20-30`, 20 backbones.
- `c05_discontinuous_contact_unindex_all`: contact4-derived discontinuous site V set, `unindex` intent, `ALL` motif heavy atoms. This condition is validation-gated and must not run on GPU unless the current wrapper can represent and normalize it cleanly.

Run:

```bash
bash examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/rfd3_contact_motif_pilot/run_rfd3_contact_motif_pilot.sh
```

Phase 2 production is intentionally out of scope.
