# Protein Design Environment Report

Checked on: 2026-06-28 16:35-16:45 Asia/Shanghai
Cluster: TYL SLURM cluster via `ssh tyl-cluster`
Deployment root: `/public/home/yinyifan/protein_design`
Legacy reusable root: `/public/home/yinyifan/protein-design`

## Summary

The cluster is suitable for a modular protein design stack, with SLURM 24.05.0, RTX 3090 and A40 GPU partitions, NVIDIA driver 550.78, CUDA driver API 12.4, Apptainer/Singularity 1.3.2, and a system PyTorch module that works on GPU. A reusable legacy RFdiffusion/ProteinMPNN installation already existed under `/public/home/yinyifan/protein-design`; the new requested layout under `/public/home/yinyifan/protein_design` now symlinks to those assets instead of duplicating large weights.

Fully smoke-tested today:

| Module | Status | Evidence |
| --- | --- | --- |
| SLURM | PASS | `sinfo -V` returned `slurm 24.05.0`. |
| GPU allocation | PASS | `srun -p Interactive --gres=gpu:rtx3090:1 nvidia-smi -L` exposed one RTX 3090 on `gpu18`. |
| Driver/CUDA | PASS | `nvidia-smi` reported driver `550.78`, CUDA `12.4`. |
| RFdiffusion import/help | PASS with wrapper | Requires `LD_LIBRARY_PATH=$HOME/protein_design/envs/rfdiffusion-se3nv/lib:$LD_LIBRARY_PATH`; then `run_inference.py --help` works. |
| RFdiffusion GPU torch | PASS | Existing env `torch 1.9.1+cu111` reported `cuda_available True`; CUDA tensor sum succeeded. |
| ProteinMPNN | PASS | System `module load pytorch/2.3.1 cuda/12.4`; two example PDBs generated one sequence each. |
| AlphaFold3 interface | PASS interface only | `/public/apps/alphafold3/alphafold3/alphafold3.sif` help works; no database/model overwrite attempted. |
| Foundry RFD3 | PASS experimental | Isolated micromamba env with `rc-foundry 0.2.0`, Python 3.12.13, torch `2.6.0+cu124`; official demo and 5TPN smoke completed. |
| Boltz repo | CLONED only | `~/protein_design/repos/boltz` at commit `b1ebfc46ecf57f5414e0d1a6f9027bbb122c53bc`; environment not installed yet. |

Source retrieval update after using the GitHub mirror fallback script:

| Module | Status | Reason / next step |
| --- | --- | --- |
| LigandMPNN | SOURCE CLONED | Repo present at commit `26ec57ac976ade5379920dbd43c7f97a91cf82de`; install in isolated env/container before use. |
| BindCraft | SOURCE CLONED | Repo present at commit `b971db42ba6e091afab63ccb30ae02215150a990`; install in isolated env/container before use. |
| RFantibody | SOURCE CLONED | Repo present at commit `8fe311415754e0276d1a39c87c57e69c88927a2d`; install in isolated env/container before use. |
| RFDiffusionAA legacy | EXPERIMENTAL LEGACY | Repo present at commit `f913a19e16f30858ce7a724fe028475b1871319c`; use backend name `rfdiffusion_all_atom_legacy`, not RF3/RFD3. |
| Foundry RFD3 | INSTALLED EXPERIMENTAL | RosettaCommons/foundry source staged at commit `62eba661f809120f0c5b3776837c61463e554c4c`; active runtime is isolated micromamba env. |
| ColabDesign local | SOURCE CLONED | Repo present at commit `e31a56fe1d9b4de25c8697f3a28b75892941cc72`; prefer separate JAX/AF2 env/container. |
| Rosetta/PyRosetta | NOT CONFIGURED | License-dependent; no existing path found in this pass. |
| Foldseek/MMseqs2/US-align/DSSP | NOT ON PATH in login check | `check_installation.sh` reports these as warnings; install via conda/container or load site modules if added later. |

## Host And Scheduler

| Item | Value |
| --- | --- |
| Login host | `admin1` |
| User | `yinyifan` |
| Home | `/public/home/yinyifan` |
| OS/kernel | Linux `4.18.0-372.9.1.el8.x86_64` |
| SLURM binary | `/opt/slurm/24.05.0/bin/sinfo` |
| SLURM version | `24.05.0` |
| Account/QOS | account `zzz`, QOS `normal` |
| Storage | `/public` Parastor, 3.0P total, 2.9P used, 188T available, 94% used |

Guardrail: do not run compute on `admin1`. Use `Interactive` for short probes and `sbatch` for production.

## Partitions Observed

| Partition | Nodes/state | GRES | CPUs/node | Memory/node |
| --- | --- | --- | --- | --- |
| `A40-autoEM` | 2 mix, 2 alloc | `gpu:a40:4` | 32 | 515377 MB |
| `A40` | 5 mix | `gpu:a40:4` | 32 | 515377 MB |
| `RTX3090-autoEM` | 2 mix, 1 alloc, 1 idle | `gpu:rtx3090:4` | 24 | 257330 MB |
| `RTX3090` | 1 mix, 3 idle | `gpu:rtx3090:4` | 24 | 257330 MB |
| `Interactive` | 1 idle | `gpu:rtx3090:4` | 24 | 257330 MB |
| `AMD` | 1 mix, 1 alloc, 2 idle | none | 128 | 1031499 MB |

## Runtime And Network

| Check | Result |
| --- | --- |
| `apptainer --version` | `apptainer version 1.3.2-1.el8` |
| `singularity --version` | `apptainer version 1.3.2-1.el8` |
| `conda` | `/public/apps/miniconda/24.4.0/bin/conda`, not on default PATH |
| `mamba/micromamba` | not found |
| Environment modules | Modules Release 5.4.0 |
| CUDA modules | `cuda/11.8`, `cuda/12.4`, `cuda/8.0` |
| PyTorch module | `pytorch/2.3.1`; in GPU job reported `torch 2.3.1 cuda 11.8 available True` |
| GitHub homepage | reachable by `curl -I` |
| HuggingFace | timed out after 8 seconds |
| Zenodo | reachable by `curl -I` |
| GitHub clone | initially unstable; a retry script with mirror fallbacks was added as `scripts/clone_with_github_mirrors.sh`; on the 2026-06-28 16:54 retry, all source repos cloned successfully before mirror fallback was needed |

## Installed / Reused Paths

| Component | Path | Notes |
| --- | --- | --- |
| New stack root | `/public/home/yinyifan/protein_design` | Created by this deployment. |
| RFdiffusion repo | `/public/home/yinyifan/protein_design/repos/RFdiffusion` | Symlink to legacy `/public/home/yinyifan/protein-design/apps/RFdiffusion`. |
| RFdiffusion env | `/public/home/yinyifan/protein_design/envs/rfdiffusion-se3nv` | Symlink to legacy env. |
| RFdiffusion weights | `/public/home/yinyifan/protein_design/weights/RFdiffusion_models` | Symlink to existing weights; no re-download. |
| ProteinMPNN repo | `/public/home/yinyifan/protein_design/repos/ProteinMPNN` | Symlink to legacy repo. |
| AlphaFold3 repo | `/public/home/yinyifan/protein_design/repos/alphafold3_system` | Symlink to `/public/apps/alphafold3/alphafold3`. |
| AlphaFold3 containers | `/public/home/yinyifan/protein_design/containers/alphafold3*.sif` | Symlinks to system SIFs. |
| Boltz repo | `/public/home/yinyifan/protein_design/repos/boltz` | Cloned; install not performed. |
| LigandMPNN repo | `/public/home/yinyifan/protein_design/repos/LigandMPNN` | Source cloned; environment not installed. |
| BindCraft repo | `/public/home/yinyifan/protein_design/repos/BindCraft` | Source cloned; environment not installed. |
| RFantibody repo | `/public/home/yinyifan/protein_design/repos/RFantibody` | Source cloned; environment not installed. |
| RFDiffusionAA legacy repo | `/public/home/yinyifan/protein_design/repos/rf_diffusion_all_atom` | Legacy Baker all-atom backend; use stack name `rfdiffusion_all_atom_legacy`, not RF3/RFD3. |
| Foundry RFD3 repo | `/public/home/yinyifan/protein_design/repos/foundry` | Source staged from RosettaCommons/foundry commit `62eba661f809120f0c5b3776837c61463e554c4c`. |
| Foundry RFD3 env | `/public/home/yinyifan/protein_design/envs/foundry-rfd3` | Isolated micromamba env; `rc-foundry 0.2.0`, Python 3.12.13, torch `2.6.0+cu124`. |
| Foundry RFD3 weights | `/public/home/yinyifan/protein_design/weights/foundry/rfd3_latest.ckpt` | Installed by `foundry install rfd3`; no duplicate copies. |
| ColabDesign repo | `/public/home/yinyifan/protein_design/repos/ColabDesign` | Source cloned; environment not installed. |

## Smoke Test Commands And Output Summary

### GPU / CUDA

Command:

```bash
srun -p Interactive -N1 -n1 --gres=gpu:rtx3090:1 --time=00:05:00 nvidia-smi
```

Summary: ran on `gpu18`; exposed `NVIDIA GeForce RTX 3090`; driver `550.78`; CUDA Version `12.4`; 24576 MiB memory.

### RFdiffusion GPU import

Command:

```bash
export LD_LIBRARY_PATH=/public/home/yinyifan/protein_design/envs/rfdiffusion-se3nv/lib:$LD_LIBRARY_PATH
/public/home/yinyifan/protein_design/envs/rfdiffusion-se3nv/bin/python - <<'PY'
import torch
print(torch.__version__, torch.version.cuda, torch.cuda.is_available())
print(torch.cuda.get_device_name(0))
print(float(torch.ones((4,4), device="cuda").sum().item()))
PY
```

Summary: `torch 1.9.1+cu111`, CUDA available `True`, device `NVIDIA GeForce RTX 3090`, tensor sum `16.0`.

### RFdiffusion inference wrapper

Command:

```bash
LD_LIBRARY_PATH=/public/home/yinyifan/protein_design/envs/rfdiffusion-se3nv/lib:$LD_LIBRARY_PATH \
  /public/home/yinyifan/protein_design/envs/rfdiffusion-se3nv/bin/python \
  /public/home/yinyifan/protein_design/repos/RFdiffusion/scripts/run_inference.py --help
```

Summary: without the env `libstdc++`, SciPy failed with `GLIBCXX_3.4.26 not found`; with the env library path, Hydra help printed successfully.

### ProteinMPNN

Command:

```bash
module purge || true
module load pytorch/2.3.1 cuda/12.4 || true
cd /public/home/yinyifan/protein_design/repos/ProteinMPNN
python helper_scripts/parse_multiple_chains.py \
  --input_path=inputs/PDB_monomers/pdbs/ \
  --output_path=/public/home/yinyifan/protein_design_probe_logs/mpnn_parsed.jsonl
python protein_mpnn_run.py \
  --jsonl_path /public/home/yinyifan/protein_design_probe_logs/mpnn_parsed.jsonl \
  --out_folder /public/home/yinyifan/protein_design_probe_logs/mpnn_smoke_out \
  --num_seq_per_target 1 --sampling_temp 0.1 --seed 37 --batch_size 1
```

Summary: generated one sequence for `5L33` in 0.4835 s and one for `6MRR` in 0.1869 s; output FASTA files were created.

### AlphaFold3 Interface

Command:

```bash
apptainer exec /public/apps/alphafold3/alphafold3/alphafold3.sif \
  python /app/alphafold/run_alphafold.py --help
```

Summary: help printed successfully. Defaults show `--db_dir=/public/home/yinyifan/public_databases` and `--model_dir=/public/home/yinyifan/models`. Databases/model weights were not downloaded or overwritten.

## Epitope Scaffold Closed-Loop Update

Added on 2026-06-28:

- `scripts/make_fixed_positions_jsonl.py`: generates ProteinMPNN fixed-position JSONL from motif TSV plus optional RFdiffusion `.trb` mapping.
- `scripts/pdb_metrics.py`: parses PDB files, computes motif Kabsch RMSD, mean PDB b-factor pLDDT proxy, and simple heavy-atom clash counts.
- `scripts/filter_designs.py`: merges AF/AF3/Boltz-style JSON confidence outputs with predicted PDB geometry metrics and writes `filter_summary.csv`.
- `scripts/make_af3_json_inputs.py`: converts ProteinMPNN FASTA records into AF3 JSON jobs.
- `scripts/slurm_templates/run_epitope_scaffold_array.sbatch`: array template for per-backbone fixed-position ProteinMPNN and per-design filtering.

Local syntax and synthetic closed-loop test:

```bash
python3 -m py_compile scripts/*.py
for f in scripts/slurm_templates/*.sbatch; do bash -n "$f"; done
python3 scripts/make_fixed_positions_jsonl.py \
  --pdb_dir ../test_epitope_loop/backbones \
  --motif_tsv ../test_epitope_loop/motif.tsv \
  --output_jsonl ../test_epitope_loop/fixed_positions.jsonl \
  --strict
python3 scripts/filter_designs.py \
  --input_dir ../test_epitope_loop/predictions \
  --pdb_dir ../test_epitope_loop/predictions \
  --reference_pdb ../test_epitope_loop/reference.pdb \
  --motif_tsv ../test_epitope_loop/motif.tsv \
  --min_plddt 70 --max_pae 10 --max_motif_rmsd 0.1 --max_clashes 20 \
  --output_csv ../test_epitope_loop/summary.csv
```

Summary: syntax checks passed; fixed-position JSONL was `{"design_0": {"A": [1, 2, 3]}}`; motif RMSD was approximately `1.1e-15`; summary CSV marked the design `PASS`.

TYL lightweight validation on `admin1`:

```bash
ln -sfn ~/protein_design/repos/RFdiffusion/examples/input_pdbs/5TPN.pdb \
  ~/protein_design/examples/epitope_scaffold/input/5TPN.pdb
cd ~/protein_design
module purge >/dev/null 2>&1 || true
module load pytorch/2.3.1 cuda/12.4 >/dev/null 2>&1 || true
PYTHONDONTWRITEBYTECODE=1 python -m py_compile scripts/*.py
for f in scripts/slurm_templates/*.sbatch; do bash -n "$f"; done
PYTHONDONTWRITEBYTECODE=1 python scripts/make_fixed_positions_jsonl.py \
  --pdb_dir examples/epitope_scaffold/input \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --output_jsonl /tmp/epitope_fixed_positions_test.jsonl \
  --strict
```

Summary: scripts compiled; SLURM templates parsed; real `5TPN.pdb` motif `A163-181` generated ProteinMPNN fixed positions `A:109-127` with empty fixed-position lists for chains `H` and `L`. No RFdiffusion/ProteinMPNN/AF3 production compute was run on the login node.

## 5TPN End-to-End Epitope Scaffold Test

Run directory:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/e2e_20260628_180440
```

Submitted Slurm chain:

```text
RFdiffusion 123129 -> ProteinMPNN 123130 -> AF3 predict 123133 -> filter 123134
```

An initial AF3 prediction attempt, `123131`, failed because the AF3 container
could not see `/public/shared/alphafold3/models`. The live filesystem and GBrain
record agreed that the models exist at `/public/shared/alphafold3/models`; the
fix was to add explicit Apptainer binding:

```text
AF3_BIND=/public/shared/alphafold3:/public/shared/alphafold3
AF3_SIF=/public/apps/alphafold3/alphafold3/alphafold3.0.1.sif
AF3_MODEL_DIR=/public/shared/alphafold3/models
AF3_DB_DIR=/public/shared/alphafold3
AF3_EXTRA_ARGS=--run_data_pipeline=False
```

Final job status:

```text
123129 rfdiff_epitope COMPLETED 00:01:34 gpu14
123130_1 epi_array COMPLETED 00:00:08 gpu14
123133_1 epi_array COMPLETED 00:01:14 gpu14
123134_1 epi_array COMPLETED 00:00:02 gpu14
```

Artifacts retained in the repo under:

```text
examples/epitope_scaffold/e2e_5tpn_20260628/
```

Key result from `filter_summary.csv`:

```text
design_id=design_0
plddt_mean=82.34062381852551
pae_mean=5.001297577854671
motif_rmsd=1.8237526412014622
motif_atoms_compared=76
motif_atoms_missing=0
clash_count=0
pass=PASS
```

## 5TPN Batch Stability Test

Run directory:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/batch_stability_20260628_182526
```

Parameters:

```text
RFdiffusion backbones: 10
ProteinMPNN sequences per backbone: 4
AF3 predictions per backbone: top 1 by ProteinMPNN score
Filter thresholds: pLDDT >= 70, PAE <= 10, motif RMSD <= 2.5 A, clash_count <= 20
```

Resource routing:

- RFdiffusion: one GPU job, `123135`.
- ProteinMPNN: GPU array, `123136_[1-10]`.
- AF3: GPU array, `123137_[1-10]`, with targeted retry `123160_6`.
- Filtering: CPU/AMD array, `123161_[1-10]`.
- Merge/ranking: CPU/AMD job, `123162`.

The initial filter submission reused the GPU array template. It was cancelled
before running and replaced with `scripts/slurm_templates/run_epitope_scaffold_filter.sbatch`,
which uses the AMD partition and no GPU request. This is the preferred Slurm
shape for the heterogeneous pipeline: use dependencies and arrays, but request
resources by stage instead of holding one large allocation for all stages.

Stability outcome:

```text
RFdiffusion outputs: 10 / 10
ProteinMPNN FASTA outputs: 10 / 10
AF3 first pass: 9 / 10 completed, 1 / 10 failed
AF3 retry: 1 / 1 completed
Final prediction outputs: 10 / 10
Filter summaries: 10 / 10
Filter PASS rows: 9 / 10
Filter FAIL rows: 1 / 10
```

First-pass AF3 failure: `123137_6` failed on `gpu15` because JAX inside the AF3
container reported no visible CUDA device, even though `nvidia-smi` in the job
could see a GPU. A targeted retry, `123160_6`, completed on `gpu14`.

Top design by pLDDT descending, PAE ascending, motif RMSD ascending, and
clash_count ascending:

```text
design_0: pLDDT=89.8871, PAE=2.9344, motif RMSD=0.9535, clash_count=0, PASS
```

Artifacts retained under:

```text
examples/epitope_scaffold/batch_stability_5tpn_20260628/
```

Artifact paths in the committed example bundle:

```text
examples/epitope_scaffold/batch_stability_5tpn_20260628/run_params.json
examples/epitope_scaffold/batch_stability_5tpn_20260628/job_ids.env
examples/epitope_scaffold/batch_stability_5tpn_20260628/logs/
examples/epitope_scaffold/batch_stability_5tpn_20260628/reports/job_accounting.tsv
examples/epitope_scaffold/batch_stability_5tpn_20260628/reports/all_filter_summary.csv
examples/epitope_scaffold/batch_stability_5tpn_20260628/reports/top_designs.csv
examples/epitope_scaffold/batch_stability_5tpn_20260628/reports/run_report.json
examples/epitope_scaffold/batch_stability_5tpn_20260628/array_work/design_*/filter_summary.csv
```

Merged reports are stored in the `reports/` subdirectory rather than duplicated
at the run root. This keeps summary artifacts separate from per-design
`array_work/` directories and raw RFdiffusion outputs.

Formal batch template added:

```bash
cd ~/protein_design
NUM_DESIGNS=20 NUM_SEQ=4 PREDICT_MAX_RECORDS=2 \
  bash scripts/slurm_templates/submit_epitope_scaffold_batch.sh
```

Supported production range: RFdiffusion `NUM_DESIGNS=10-50`, ProteinMPNN
`NUM_SEQ=4-8`, AF3 `PREDICT_MAX_RECORDS=2` top scored sequences per backbone.
The template submits a resource-specific dependency DAG:

```text
RFdiffusion GPU job -> ProteinMPNN GPU array -> AF3 GPU array -> CPU filter array -> CPU merge/ranking job
```

AF3 failure retry operation:

```bash
cd ~/protein_design
RUN_ROOT=/path/to/batch_run PRED_JOB=<first-pass-af3-array-job-id> \
  bash scripts/retry_failed_af3_predictions.sh
```

This helper uses `sacct` to find failed AF3 array tasks, resubmits only those
indices, reruns CPU filtering for retried designs, and refreshes
`reports/all_filter_summary.csv`, `reports/top_designs.csv`, and
`reports/run_report.json`.

## Foundry RFD3 Backend Update

Foundry was installed in an isolated user-space micromamba runtime without
touching the stable RFdiffusion v1 or ProteinMPNN environments.

```text
Install job: 123260
Torch CUDA repair job: 123262
Official Foundry RFD3 demo smoke: 123263, completed
5TPN Foundry RFD3 backbone smoke: 123264, completed
5TPN downstream smoke: ProteinMPNN 123265, AF3 123266, filter 123267, merge 123268
```

Three-way 5TPN comparison:

```text
Run root: /public/home/yinyifan/protein_design/examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554
Backends: rfdiffusion_v1, rfdiffusion_all_atom_legacy, foundry_rfd3
Final PASS rates: rfdiffusion_v1 9/10, rfdiffusion_all_atom_legacy 0/10, foundry_rfd3 4/10
Reports: reports/backend_comparison.csv, reports/backend_comparison.md, reports/run_report.json
```

Details are in `docs/foundry_rfd3_backend_report.md`.

## Prediction Backend Decoupling Update

AF3 remains the primary prediction backend. The stack now has a predictor-neutral
canonical input layer and optional RF3/Boltz adapters for AF3 top candidates.
AF3 `*_data.json` files are explicitly treated as AF3 Stage 2 assets only, not
as cross-model interchange files.

New scripts and templates:

```text
scripts/make_canonical_prediction_inputs.py
scripts/extract_af3_stage1_assets.py
scripts/make_rf3_json_inputs.py
scripts/make_boltz_inputs.py
scripts/compare_prediction_backends.py
scripts/slurm_templates/run_af3_stage1.sbatch
scripts/slurm_templates/run_af3_inference.sbatch
scripts/slurm_templates/run_rf3_predict.sbatch
scripts/slurm_templates/run_boltz_predict.sbatch
```

Top-3 5TPN cross-validation test:

```text
Run root: examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628
AF3 status: existing primary predictions reused; design_9/design_1/design_4 all PASS
RF3 jobs: 123381 failed due invalid override; 123383 retried and failed due missing RF3 checkpoint
Boltz job: 123382 failed because the boltz command/environment is not installed
Consensus: reports/consensus_summary.csv
```

RF3 and Boltz native input generation passed:

```text
prediction_inputs/rf3/*.rf3.json
prediction_inputs/boltz/*.boltz.yaml
```

Optional cross-validation is blocked until:

```text
RF3: ~/protein_design/weights/foundry/rf3_foundry_01_24_latest_remapped.ckpt exists
Boltz: an isolated env/container provides the boltz command
```

Details are in `docs/cross_model_prediction_report.md`.

## Recommendations

1. Use original RFdiffusion as the stable backbone/motif generator and keep `LD_LIBRARY_PATH` wrapper in all launch scripts.
2. Use the system `pytorch/2.3.1` module for ProteinMPNN unless a dedicated conda env is later needed.
3. Treat AlphaFold3 as a configured site interface only; verify database/model paths with the cluster owner before production runs.
4. Treat Foundry RFD3 as an experimental backbone backend and compare it side-by-side with RFdiffusion v1 before production use.
5. Keep `rfdiffusion_all_atom_legacy` as a legacy all-atom backend; do not call it RF3/RFD3.
6. Install BindCraft, RFantibody, LigandMPNN, and ColabDesign from the cloned source trees only in separate envs/containers.
7. Do not duplicate AF/RF databases or weights on `/public`, which is already 94% used.
