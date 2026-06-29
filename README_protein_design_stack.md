# TYL Protein Design Stack

This file mirrors the root README for cluster-side installs where users expect
`README_protein_design_stack.md` as the entrypoint.

See `README.md` for the current reusable workflow, supported backends, minimal
examples, ignored runtime artifacts, and links to:

- `docs/training_epitope_scaffold_workflow_for_humans.md`
- `skills/epitope_scaffold_design/SKILL.md`
- `docs/protein_design_env_report.md`
- `docs/foundry_rfd3_backend_report.md`
- `docs/cross_model_prediction_report.md`
- `docs/fold_clustering_report.md`
- `docs/pre_order_qc_report.md`

The supported production scaffold-generation backends are RFdiffusion v1 and
Foundry RFD3. Foundry RF3 is used only for prediction/folding confirmation.
Benchmark runtime outputs and final candidate packages are not tracked in git.
