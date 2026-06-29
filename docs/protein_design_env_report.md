# Protein Design Environment Report

Cluster root: `/public/home/yinyifan/protein_design`

This report is kept as an environment and reproducibility summary. Runtime
benchmark outputs, logs, prediction trees, and candidate packages are not tracked
in git.

## Cluster Summary

| Item | Status |
| --- | --- |
| Scheduler | SLURM 24.05.0 |
| GPU partitions | RTX3090 and A40 partitions observed |
| Driver/CUDA | NVIDIA driver 550.78, CUDA driver API 12.4 |
| Container runtime | Apptainer/Singularity 1.3.2 |
| AF3 | Site container interface available; databases/weights are shared paths and must not be overwritten |
| RFdiffusion v1 | Reuses existing user-space environment and weights |
| ProteinMPNN | Reuses existing repo/module path |
| Foundry RFD3 | Isolated micromamba env, `rc-foundry 0.2.0`, Python 3.12.13, torch `2.6.0+cu124` |
| Foundry RF3 | Prediction/folding backend, optional confirmation |
| Boltz | Optional validation backend; no-MSA mode is warning only until task-specific validation |
| LigandMPNN | Source cloned or optional install; keep isolated from ProteinMPNN baseline |
| BindCraft/RFantibody | Source-only placeholders; install later in isolated runtimes |

## Guardrails

- Do not compute on login or management nodes.
- Use SLURM for GPU work.
- Do not modify system Python or base conda.
- Do not duplicate large weights/databases in the repository.
- Keep RFdiffusion v1, Foundry RFD3, AF3/RF3/Boltz, binder, and antibody
  runtimes isolated.

## Reusable Workflow Status

The reusable epitope scaffold stack now supports:

1. Motif extraction and validation.
2. Backbone generation with RFdiffusion v1 or Foundry RFD3.
3. ProteinMPNN fixed-position sequence design.
4. Canonical prediction input generation.
5. AF3 primary prediction plus optional RF3/Boltz cross-validation.
6. Motif/confidence/clash filtering.
7. Contact-face QC.
8. Fold and sequence diversity clustering.
9. Optional phage display QC.
10. Pre-order QC and final candidate packaging.

See `README.md`, `skills/epitope_scaffold_design/SKILL.md`, and
`docs/training_epitope_scaffold_workflow_for_humans.md`.
