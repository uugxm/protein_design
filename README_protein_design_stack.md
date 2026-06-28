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

Primary path:

1. RFdiffusion motif scaffolding or partial diffusion.
2. ProteinMPNN sequence design with motif positions fixed from RFdiffusion `.trb` mappings.
3. AF2/AF3/Boltz prediction.
4. Motif RMSD, pLDDT, pTM/ipTM, PAE and clash filtering to `filter_summary.csv`.

Minimal launch:

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

Batch stability / production launch:

```bash
cd ~/protein_design
NUM_DESIGNS=20 NUM_SEQ=4 PREDICT_MAX_RECORDS=2 \
  bash scripts/slurm_templates/submit_epitope_scaffold_batch.sh
```

The formal batch template supports `NUM_DESIGNS=10-50`, `NUM_SEQ=4-8`, and AF3
top-2 predictions per backbone by default. It writes `run_params.json`,
`job_ids.env`, `backbone_list.txt`, logs, per-design `filter_summary.csv`
files, and merged ranking outputs under one run directory:

```text
reports/all_filter_summary.csv
reports/top_designs.csv
reports/run_report.json
```

The Slurm shape is a dependency DAG, not one long monolithic allocation:

```text
RFdiffusion GPU job
  -> ProteinMPNN GPU array
  -> AF3 GPU array
  -> CPU filter array
  -> CPU merge/ranking job
```

AF3 retry mechanism:

```bash
cd ~/protein_design
RUN_ROOT=/path/to/batch_run PRED_JOB=<first-pass-af3-array-job-id> \
  bash scripts/retry_failed_af3_predictions.sh
```

The retry helper uses `sacct` to find failed AF3 array indices, resubmits only
those prediction tasks, reruns CPU filtering for the retried indices, and
submits a fresh CPU merge job. This is intended for transient JAX/CUDA visibility
or node-local AF3 failures; persistent input errors should be fixed before
retrying.

## ProteinMPNN Sequence Design

ProteinMPNN is reused from the existing legacy repo and runs with the cluster PyTorch module:

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

Unified filtering script:

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

Use separate envs/containers:

| Module | Suggested isolation |
| --- | --- |
| LigandMPNN | own conda/env or Apptainer image |
| RFdiffusion all-atom / RFdiffusion3-style interfaces | separate from original RFdiffusion |
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
