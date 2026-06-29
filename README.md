# TYL Protein Design Stack

Reusable protein-design workflow repository for the TYL SLURM cluster.

This repository is intentionally a tools, templates, and documentation repo. It
does not track benchmark prediction trees, candidate PDB/CIF packages, cluster
logs, model weights, databases, or other runtime evidence by default.

## What This Repository Does

The stack supports modular protein-design workflows:

- Epitope scaffold and motif scaffolding.
- De novo binder workflow stubs, kept separate from epitope scaffolding.
- Antibody/nanobody workflow stubs, kept in isolated environments.
- Sequence design, prediction, filtering, clustering, display QC, pre-order QC,
  and candidate packaging utilities.

## Supported Backends

| Stage | Supported backend |
| --- | --- |
| Backbone generation | RFdiffusion v1, Foundry RFD3 |
| Sequence design | ProteinMPNN, optional LigandMPNN |
| Primary prediction | AlphaFold3 |
| Optional confirmation | Foundry RF3 |
| Optional warning cross-check | Boltz |

RFdiffusion v1 is the stable baseline for continuous motif scaffolding. Foundry
RFD3 is the experimental all-atom/contact-aware generation backend. Foundry RF3
is a folding/prediction backend, not a backbone generator.

## Recommended Backend Selection

| Task | Recommended route |
| --- | --- |
| Continuous short motif | RFdiffusion v1 -> ProteinMPNN -> AF3 |
| Contact-sensitive continuous motif | RFdiffusion v1 and Foundry RFD3 side by side |
| Discontinuous epitope/contact core | Foundry RFD3, with explicit motif provenance |
| Protein-only sequence design | ProteinMPNN |
| Ligand, cofactor, metal, glycan, nucleic-acid context | LigandMPNN where available |
| High-priority prediction confirmation | AF3 primary plus RF3 confirmation |
| Boltz validation | Warning/cross-check only until task-specific MSA/template mode is tested |

## Quick Start

On the login node, run only lightweight checks:

```bash
cd ~/protein_design
bash scripts/check_installation.sh
```

GPU work must go through SLURM:

```bash
srun -p Interactive -N1 -n1 --gres=gpu:rtx3090:1 --time=00:05:00 nvidia-smi -L
```

Prepare a new epitope scaffold run from a complex:

```bash
python scripts/prepare_epitope_from_complex.py \
  --complex_pdb /path/to/complex.pdb \
  --antigen_chain A \
  --binder_chains H,L \
  --contact_cutoff 4.5 \
  --out_dir runs/my_epitope/input

python scripts/validate_motif_definition.py \
  --reference_pdb runs/my_epitope/input/reference.pdb \
  --motif_tsv runs/my_epitope/input/motif_residues.tsv \
  --out_dir runs/my_epitope/input_validation
```

Launch the backbone stage:

```bash
BACKBONE_BACKEND=rfdiffusion_v1 \
INPUT_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
RUN_ROOT=/path/to/run \
NUM_DESIGNS=20 \
  sbatch scripts/slurm_templates/run_backbone_generation.sbatch
```

For Foundry RFD3:

```bash
BACKBONE_BACKEND=foundry_rfd3 \
FOUNDRY_RFD3_FIXED_ATOMS=ALL \
INPUT_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
RUN_ROOT=/path/to/run_rfd3 \
NUM_DESIGNS=20 \
  sbatch scripts/slurm_templates/run_backbone_generation.sbatch
```

For a full reusable orchestration wrapper, use:

```bash
python scripts/run_epitope_scaffold_workflow.py --help
```

## Directory Layout

```text
~/protein_design/
  envs/          environment notes, not full env directories
  repos/         external source repositories, not committed here
  weights/       model-weight symlinks or README notes only
  containers/    Apptainer/Singularity image symlinks or README notes only
  databases/     database symlinks or README notes only
  scripts/       workflow tools, adapters, QC, and SLURM templates
  examples/      minimal templates, not benchmark result trees
  docs/          method docs, deployment reports, training material
  skills/        reusable Codex workflow skill instructions
```

## Required External Tools And Weights

Weights and databases are site-local and should be configured by path:

- RFdiffusion v1 repository and checkpoint.
- Foundry RFD3/RF3 environment and checkpoints.
- ProteinMPNN repository or module.
- AlphaFold3 container, model directory, and database directory.
- Optional Boltz runtime/cache.
- Optional LigandMPNN, Rosetta/PyRosetta, Foldseek/MMseqs2, US-align.

Do not download or overwrite large shared AF3 databases, model weights, or
cluster-managed software from this repository.

## Minimal Example Inputs

The tracked `examples/` directory contains small templates only:

- `examples/epitope_scaffold/motif_residues.tsv`
- `examples/epitope_scaffold/rfdiffusion_params.env`
- `examples/epitope_scaffold/filter_thresholds.env`
- `examples/binder_design/hotspots.tsv`
- `examples/antibody_design/epitope_residues.tsv`

Bring your own reference PDB/CIF or generate a motif definition from a complex
with `scripts/prepare_epitope_from_complex.py`.

## Outputs

Production runs should write into an untracked run directory. Standard outputs
include:

- `run_params.json`
- `input_validation.csv` and `motif_definition_report.md`
- `rfdiffusion_outputs/design_*.pdb` and mapping files
- ProteinMPNN/LigandMPNN sequence outputs
- canonical prediction inputs
- AF3/RF3/Boltz model-specific inputs and prediction outputs
- `filter_summary.csv` or `all_filter_summary.csv`
- `contact_face_qc.csv`
- `fold_clustering/diverse_shortlist.csv`
- `phage_display_qc.csv` when relevant
- `pre_order_qc.csv`
- final candidate summaries/packages when explicitly requested

These outputs are runtime artifacts and are ignored by default.

## Human Training And Skill Docs

- Human training guide: `docs/training_epitope_scaffold_workflow_for_humans.md`
- Codex workflow skill: `skills/epitope_scaffold_design/SKILL.md`

## What Is Intentionally Not Tracked

The repository ignores runtime outputs such as `logs/`, `raw_outputs/`,
`predictions/`, AF3/RF3/Boltz/Foundry/ProteinMPNN output trees, final candidate
packages, benchmark run directories, SLURM logs, `.cif`, `.cif.gz`, `.trb`,
`.pkl`, `.npz`, checkpoint files, containers, weights, and databases.

## Deprecated / Removed

The old Baker RFDiffusionAA / all-atom legacy integration has been removed from
the supported workflow. Use Foundry RFD3 for all-atom/contact-aware backbone
generation and Foundry RF3 for folding/prediction confirmation.
