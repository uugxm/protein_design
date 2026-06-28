# Reproducibility Boundary

This repository records the TYL protein-design deployment plan, launch scripts,
SLURM templates, smoke-test summaries, and third-party source commit hashes.

It intentionally does not vendor:

- third-party source repositories under `~/protein_design/repos`
- model weights
- AlphaFold databases
- Apptainer/Singularity images
- generated design outputs

Use `docs/repo_commits.tsv` and `scripts/clone_with_github_mirrors.sh` to
reconstruct the source tree on the cluster.

