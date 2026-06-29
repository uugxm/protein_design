# TYL Protein Design Stack

Root on cluster: `/public/home/yinyifan/protein_design`

This stack is modular by design. It separates epitope/motif scaffolding, de novo binder design, antibody/nanobody design, sequence design, prediction/filtering, and general structural analysis so that CUDA/JAX/PyTorch/Rosetta dependencies do not collide.

## Layout

```text
~/protein_design/
  envs/          conda/env symlinks and environment notes
  repos/         git repositories and symlinks to existing repos
  weights/       model-weight symlinks only
  containers/    Apptainer/Singularity SIF symlinks
  databases/     database symlinks only
  scripts/       unified launch, filtering, and SLURM templates
  examples/      minimal task examples
  docs/          deployment report and failure log
```

## Quick Check

On the login node, only run lightweight checks:

```bash
cd ~/protein_design
bash scripts/check_installation.sh
```

If GitHub clone is unstable, use the retry script with mirror/proxy fallbacks:

```bash
cd ~/protein_design
bash scripts/clone_with_github_mirrors.sh
```

GPU checks and model runs must go through SLURM:

```bash
srun -p Interactive -N1 -n1 --gres=gpu:rtx3090:1 --time=00:05:00 nvidia-smi -L
```

## Epitope Scaffold / Motif Scaffolding

Goal: stabilize and display a known motif/epitope on a new scaffold. This is not the same as binder design.

Current reusable entrypoint: `skills/epitope_scaffold_design/SKILL.md`.

Current official benchmark: `examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/`.

Run the Phase 1 smoke benchmark wrapper from the repository root:

```bash
cd ~/protein_design
bash examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/run_smoke_benchmark.sh
```

The old smoke-test directory `examples/epitope_scaffold/` is retained as historical smoke-test provenance. It is not the current runnable entrypoint; cleanup should be handled in a separate PR if it is still desired.

Canonical workflow shape:

1. RFdiffusion motif scaffolding or partial diffusion.
2. ProteinMPNN sequence design with motif positions fixed from RFdiffusion `.trb` mappings.
3. AF2/AF3/Boltz prediction.
4. Motif RMSD, pLDDT, pTM/ipTM, PAE and clash filtering to `filter_summary.csv`.

Legacy low-level command snippets, retained only for historical `examples/epitope_scaffold/` reference:

```bash
cd ~/protein_design/examples/epitope_scaffold
sbatch ../../scripts/slurm_templates/run_rfdiffusion_epitope.sbatch
```

Then generate a task list and run fixed-position ProteinMPNN as an array:

```bash
find "$PWD/rfdiffusion_outputs" -maxdepth 1 -name '*.pdb' | sort > backbone_list.txt
TASK_LIST=$PWD/backbone_list.txt STAGE=mpnn \
  sbatch --array=1-$(wc -l < backbone_list.txt) \
  ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

Key environment detail: RFdiffusion must use its env library path:

```bash
export LD_LIBRARY_PATH=~/protein_design/envs/rfdiffusion-se3nv/lib:$LD_LIBRARY_PATH
```

## ProteinMPNN Sequence Design

ProteinMPNN is reused from the existing legacy repo and runs with the cluster PyTorch module. The command below is a legacy low-level reference; current benchmark runs should use the reusable skill wrapper above.

```bash
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
cd ~/protein_design/examples/epitope_scaffold
PDB_DIR=$PWD/backbones OUT_DIR=$PWD/mpnn_outputs \
  sbatch ../../scripts/slurm_templates/run_proteinmpnn.sbatch
```

For fixed motif residues, generate ProteinMPNN fixed-position JSONL with the helper scripts in `repos/ProteinMPNN/helper_scripts/`.
This stack adds `scripts/make_fixed_positions_jsonl.py`, which reads the motif
TSV plus RFdiffusion `.trb` files and writes ProteinMPNN-compatible fixed
positions automatically.

## Structure Prediction / Filtering

AlphaFold3 is available as a site container interface:

```bash
apptainer exec ~/protein_design/containers/alphafold3.sif \
  python /app/alphafold/run_alphafold.py --help
```

Do not download or overwrite AF3 databases/weights. Confirm these paths before production:

```text
--db_dir=/public/home/yinyifan/public_databases
--model_dir=/public/home/yinyifan/models
```

Unified filtering script, legacy low-level reference:

```bash
python ~/protein_design/scripts/filter_designs.py \
  --input_dir predictions \
  --pdb_dir predictions \
  --reference_pdb examples/epitope_scaffold/input/5TPN.pdb \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --trb_dir examples/epitope_scaffold/rfdiffusion_outputs \
  --output_csv filter_summary.csv
```

The current script extracts common JSON confidence fields and computes motif RMSD
and clash count from predicted PDB files.

## Binder Design

Goal: design a new protein binder against a target surface/hotspot. This must stay separate from epitope scaffolding.

Template:

```bash
cd ~/protein_design/examples/binder_design
TARGET_PDB=input/target.pdb TARGET_CHAIN=A HOTSPOTS=A45,A46,A47 \
  sbatch ../../scripts/slurm_templates/run_bindcraft.sbatch
```

Current status: BindCraft source is cloned under `~/protein_design/repos/BindCraft`; its isolated runtime environment is not installed yet. The SLURM template records the expected target-chain-hotspot interface and exits with a clear message until the repo environment is configured.

## Antibody / Nanobody Design

Goal: support VHH/scFv/CDR loop design against an antigen epitope while preserving antibody numbering/framework constraints.

Template:

```bash
cd ~/protein_design/examples/antibody_design
ANTIGEN_PDB=input/antigen.pdb EPITOPE=A100,A101,A102 \
  sbatch ../../scripts/slurm_templates/run_rfantibody.sbatch
```

Current status: RFantibody source is cloned under `~/protein_design/repos/RFantibody`; its isolated runtime environment is not installed yet. Recommended auxiliary isolated env: ANARCI/AbNumber, ImmuneBuilder or ABodyBuilder2, Biopython, pdb-tools, and PyMOL-open-source or ChimeraX if available.

## Optional Modules To Install Later

## Backbone Backend Status

RFdiffusion v1 is the stable epitope scaffold baseline. The old
`rf_diffusion_all_atom` integration is retained only as
`rfdiffusion_all_atom_legacy`; it is not Foundry RF3/RFD3. Foundry RFD3 is
available as experimental `BACKBONE_BACKEND=foundry_rfd3` through the unified
backbone launcher. The 5TPN three-way comparison is saved under
`examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/`;
details are in `docs/foundry_rfd3_backend_report.md`.

Use separate envs/containers:

| Module | Suggested isolation |
| --- | --- |
| LigandMPNN | own conda/env or Apptainer image |
| RFDiffusionAA legacy / Foundry RFD3 | separate from original RFdiffusion |
| ColabDesign | separate JAX/AF2 env/container |
| BindCraft | container or project env pinned to its release |
| RFantibody | antibody-specific env/container |
| Boltz | fresh env, e.g. `pip install boltz[cuda]` after testing package access |
| Rosetta/PyRosetta | license-managed installation only |

## Reproducibility Notes

- No sudo was used.
- System Python and base conda were not modified.
- Large weights/databases are symlinked, not duplicated.
- Actual test outputs and failures are recorded in `docs/protein_design_env_report.md`.
- Use `sbatch` for production and `Interactive` only for short probes.
