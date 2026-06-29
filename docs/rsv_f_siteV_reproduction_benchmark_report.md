# RSV F Site V / hRSV90 Reproduction Benchmark Report

Benchmark directory: `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/`

## Status

Phase 1 smoke benchmark is complete. Phase 2 production benchmark has not been started; it should only run after this Phase 1 report is reviewed.

The previous 5TPN test run is treated only as a skill smoke test. The formal benchmark input was rebuilt from PDB 5TPN and reconciled against the original RFdiffusion motif-scaffolding example.

The old smoke-test directory `examples/epitope_scaffold/` was removed after required inputs, motif definitions, reports, and final candidate package artifacts were migrated into the new benchmark directory. The new skill and benchmark do not depend on the old directory.

## Motif Input Reconstruction

The RSV F/hRSV90/site V motif input was reconstructed from PDB 5TPN with two evidence layers:

- Contact extraction from the antigen-antibody complex using chain `A` as antigen and chains `H/L` as hRSV90 heavy/light chains.
- Original RFdiffusion example reconciliation against RosettaCommons RFdiffusion commit `2d0c003df46b9db41d119321f15403dec3716cd9`.

RCSB 5TPN confirms chain `A` is an engineered RSV F/fibritin construct, chain `H` is hRSV90 heavy chain, and chain `L` is hRSV90 light chain. Contact-derived epitope sets were generated at 4.0 and 5.0 Angstrom heavy-atom cutoffs. These sets are discontinuous and identify a contact core overlapping `A169-A178`, plus additional distal contacts.

## RFdiffusion Case Match

The benchmark motif definition is `inputs/motif_residues_benchmark.tsv`: chain `A`, residues `163-181`, matching the official RFdiffusion motif-scaffolding example contig `[10-40/A163-181/10-40]`.

This motif is not reused from the previous 5TPN test run. It is used because the official RFdiffusion example defines the reproduction target that way, after independent complex-derived contact extraction showed how the antibody contacts relate to the continuous motif.

## Phase 1 Design

- RFdiffusion v1: 20 requested backbones.
- Foundry RFD3: 20 requested backbones.
- ProteinMPNN: 5 sequences per generated backbone in the current runnable pipeline, yielding 100 sequences per backend.
- AF3: 20 primary predictions per backend after retry normalization.
- RF3: top 5 AF3 candidates per backend.
- Downstream: filtering, fold/motif/sequence clustering, pre-order QC, and final candidate package generation.

## Backend Comparison

| Metric | RFdiffusion v1 | Foundry RFD3 |
|---|---:|---:|
| Backbones generated | 20/20 | 20/20 |
| Backbone walltime | 00:09:34 | 00:11:45 |
| GPU-minutes, Phase 1 accounting | 52.733 | 54.350 |
| AF3 PASS | 19/20 | 7/20 |
| AF3 pass rate | 0.95 | 0.35 |
| RF3 confirmed, top candidates | 5/5 | 5/5 |
| AF3 median motif RMSD | 0.995017 | 2.72062 |
| RF3 median motif RMSD | 0.815762 | 1.67669 |
| Mean pLDDT | 85.0508 | 73.0456 |
| Mean PAE | 3.98359 | 9.36123 |
| Motif atoms missing fail rate | 0 | 0 |
| Global fold clusters | 16 | 7 |
| Motif-local clusters | 19 | 7 |
| Sequence clusters | 19 | 7 |
| Success per GPU-hour | 21.6183 | 7.72769 |

In this Phase 1 benchmark, Foundry RFD3 did not improve speed, AF3 pass rate, RF3 motif RMSD, or success per GPU-hour relative to RFdiffusion v1.

## Candidate Output

Primary benchmark candidates are the RFdiffusion v1 RF3-confirmed designs:

- `rfdiffusion_v1__design_15`
- `rfdiffusion_v1__design_9`
- `rfdiffusion_v1__design_7`
- `rfdiffusion_v1__design_18`
- `rfdiffusion_v1__design_4`

Foundry RFD3 candidates are retained as comparison backups:

- `foundry_rfd3__design_6`
- `foundry_rfd3__design_14`
- `foundry_rfd3__design_16`
- `foundry_rfd3__design_0`
- `foundry_rfd3__design_4`

No cloning-ready construct table was generated. `pre_order_qc_decision.csv` marks all candidates as `order_now=no` because expression system, vector, tag/signal peptide/linker policy, restriction or assembly policy, and codon optimization policy are not specified.

## Answers

- Successfully rebuilt RSV F/hRSV90/site V motif input: yes.
- Motif definition matches the original RFdiffusion example: yes for the reconciled benchmark motif `A163-181`; no for purely contact-derived 5TPN epitope sets, which are discontinuous.
- RFdiffusion v1 performance: strong Phase 1 result, with 19/20 AF3 pass and 5/5 RF3 confirmation on selected candidates.
- Foundry RFD3 performance: generated all requested backbones but had lower AF3 pass rate and worse AF3/RF3 motif RMSD in this run.
- RFD3 faster than v1: no, 11:45 versus 9:34 backbone walltime.
- RFD3 more accurate than v1: no, higher AF3/RF3 motif RMSD and lower mean pLDDT.
- RFD3 produced more experimental candidates: no, fewer AF3-pass candidates and fewer clusters.
- Recommended designs for later experimental review: the five RFdiffusion v1 primary benchmark candidates above, pending expression/vector policy.

## Non-Comparable Factors

- Current downstream QC uses AF3 primary prediction and RF3 confirmation, which were not the original RFdiffusion paper's only evaluation layer.
- Foundry RFD3 uses a different backend and checkpoint family from RFdiffusion v1.
- Contact-derived 5TPN epitope residues are discontinuous; the official RFdiffusion reproduction motif is continuous `A163-181`.
- The 5TPN input is an engineered RSV F/fibritin construct with mutations, missing residues, linker/foldon regions, and tag annotations.
- Boltz no-MSA results, if generated later, are warnings only and are not hard gates.

## Result Files

- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/reports/backend_comparison_summary.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/reports/diverse_shortlist.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/reports/pre_order_qc_decision.csv`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/reports/final_candidate_selection_report.md`
- `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/final_candidates/package_manifest.tsv`
