# Foundry RFD3 Backend Report

Date: 2026-06-28

## Naming And Roles

Foundry is the upstream for the next-generation RosettaCommons protein-design
models:

```text
Repository: https://github.com/RosettaCommons/foundry
Inspected commit: 62eba661f809120f0c5b3776837c61463e554c4c
TYL source path: /public/home/yinyifan/protein_design/repos/foundry
Package name: rc-foundry
Installed package version: 0.2.0
```

Model roles from the Foundry README:

```text
RFD3 / RFdiffusion3: design / generation model
ProteinMPNN / LigandMPNN: inverse folding
RF3: structure prediction / folding model
```

Stack backend names:

```text
rfdiffusion_v1               stable baseline backbone generator
rfdiffusion_all_atom_legacy  legacy Baker RFDiffusionAA backend, not RF3/RFD3
foundry_rfd3                 Foundry RFdiffusion3 backbone-generation backend
foundry_rf3                  Foundry RF3 folding / prediction backend
```

The previous `baker-laboratory/rf_diffusion_all_atom` integration is therefore
kept only as `rfdiffusion_all_atom_legacy`. It must not be described as RF3 or
RFD3. RFdiffusion v1 remains the stable production baseline. `foundry_rfd3` is
experimental until broader benchmark runs are complete.

## Installation

TYL login-node inspection:

```text
conda/mamba/micromamba on default PATH: no
system python3: 3.6.8
python module available: python/3.9
Foundry Python requirement: >=3.12
Apptainer: 1.3.2
```

Two isolated installation paths were tested.

### Container Fallback

Template:

```text
scripts/slurm_templates/install_foundry_container.sbatch
```

Result:

```text
Job: 123259
Command: apptainer pull docker://rosettacommons/foundry:latest
Status: failed
Reason: registry-1.docker.io connection timed out from TYL
```

Keep this template for a future local mirror or prebuilt SIF workflow, but it is
not the active runtime on TYL.

### User-Space Micromamba Runtime

Template:

```text
scripts/slurm_templates/install_foundry_micromamba.sbatch
```

Result:

```text
Job: 123260
Status: completed
Micromamba: /public/home/yinyifan/protein_design/envs/micromamba/bin/micromamba
Environment: /public/home/yinyifan/protein_design/envs/foundry-rfd3
Python: 3.12.13
rc-foundry: 0.2.0
Initial torch: 2.12.1+cu130
Checkpoint dir: /public/home/yinyifan/protein_design/weights/foundry
Installed checkpoint: rfd3_latest.ckpt, 2.51 GB
```

The install job ran:

```bash
pip install "rc-foundry[rfd3]"
foundry list-available
foundry install rfd3 --checkpoint-dir /public/home/yinyifan/protein_design/weights/foundry
foundry list-installed
```

`foundry list-available` included:

```text
rfd3na
rfd3
rf3
proteinmpnn
ligandmpnn
rf3_preprint_921
rf3_preprint_124
solublempnn
```

`foundry list-installed` found the local RFD3 checkpoint after installation.

### CUDA Repair

The first official smoke attempt showed that torch `2.12.1+cu130` did not see a
GPU on the TYL RTX 3090 nodes:

```text
torch.cuda.is_available=False
driver CUDA shown by nvidia-smi: 12.4
```

Repair template:

```text
scripts/slurm_templates/repair_foundry_torch_cuda124.sbatch
```

Result:

```text
Job: 123262
Status: completed
Torch after repair: 2.6.0+cu124
Torch CUDA runtime: 12.4
GPU test: cuda_available=True, NVIDIA GeForce RTX 3090
pip check: no broken requirements
```

This keeps Foundry isolated from the RFdiffusion v1 and ProteinMPNN
environments.

## RFD3 Input Format

RFD3 accepts JSON/YAML InputSpecification files and Hydra-style CLI args:

```bash
rfd3 design out_dir=<outdir> inputs=<input.json> skip_existing=False prevalidate_inputs=True
```

Relevant motif-scaffolding fields from `models/rfd3/docs/input.md`:

```text
input                 path to PDB/CIF
contig                comma-separated RFD3 contig, e.g. "10-40,A163-181,10-40"
select_fixed_atoms    InputSelection for fixed coordinates, e.g. {"A163-181": "BKBN"}
select_unfixed_sequence optional InputSelection to allow sequence redesign
length                optional total length constraint
is_non_loopy          optional conditioning flag
partial_t             optional partial diffusion noise in angstroms
```

RFD3 contigs are comma-separated and use `/0` for chain breaks. They are not the
same syntax as RFdiffusion v1 slash contigs.

## Stack Adapter

New scripts:

```text
scripts/make_rfd3_motif_input.py
scripts/normalize_foundry_rfd3_outputs.py
```

`make_rfd3_motif_input.py` creates an RFD3-compatible JSON input from:

```text
reference PDB/CIF
motif TSV, e.g. A 163 181
desired designed N/C scaffold ranges, e.g. 10-40 and 10-40
fixed atom mode, e.g. BKBN
optional conditioning flags
```

For 5TPN A163-181 with default scaffold ranges, it writes:

```json
{
  "motif_scaffold": {
    "dialect": 2,
    "input": "/public/home/yinyifan/protein_design/examples/epitope_scaffold/input/5TPN.pdb",
    "contig": "10-40,A163-181,10-40",
    "select_fixed_atoms": {
      "A163-181": "BKBN"
    },
    "is_non_loopy": true
  }
}
```

`normalize_foundry_rfd3_outputs.py` converts Foundry `.cif.gz` structures to the
existing downstream layout:

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
```

The `.trb` mapping is generated by exact motif sequence matching, so the
existing fixed-position ProteinMPNN and motif RMSD code paths can be reused.

## Smoke Tests

Official Foundry demo smoke:

```text
Job: 123263
Node: gpu18
Command: rfd3 design out_dir=<test_out> inputs=<foundry>/models/rfd3/docs/examples/demo.json skip_existing=False prevalidate_inputs=True diffusion_batch_size=1 n_batches=1 inference_sampler.num_timesteps=10
Status: completed
Torch: 2.6.0+cu124
CUDA visible: true
GPU: NVIDIA GeForce RTX 3090
Structure outputs: 3 .cif.gz files plus metadata JSON
Run dir: /public/home/yinyifan/protein_design/examples/epitope_scaffold/foundry_rfd3_official_smoke_20260628_212615
```

5TPN motif backbone smoke:

```text
Job: 123264
Backend: foundry_rfd3
Motif: 5TPN chain A residues 163-181
RFD3 contig: 10-40,A163-181,10-40
Motif sequence: EVNKIKSALLSTNKAVVSL
Status: completed
Normalized outputs: 1 PDB, 1 TRB, backbone_list.txt
Run dir: /public/home/yinyifan/protein_design/examples/epitope_scaffold/foundry_rfd3_smoke_5tpn_20260628
```

Downstream smoke on the same design:

```text
ProteinMPNN job: 123265, completed, fixed motif positions A23-A41
AF3 prediction job: 123266, completed
Filter job: 123267, completed
Merge job: 123268, completed
Filter result: FAIL
pLDDT mean: 71.91
PAE mean: 18.22
Motif RMSD: 7.62
Clash count: 0
```

This confirms the Foundry RFD3 output can be parsed by ProteinMPNN and passed
through the existing AF3/filter/ranking pipeline.

## Unified Launcher

`scripts/slurm_templates/run_backbone_generation.sbatch` now accepts:

```text
BACKBONE_BACKEND=rfdiffusion_v1
BACKBONE_BACKEND=rfdiffusion_all_atom_legacy
BACKBONE_BACKEND=foundry_rfd3
```

The old `BACKBONE_BACKEND=rf3` alias is intentionally not supported, because
Foundry RF3 is a folding / prediction model, not a backbone generator.

The Foundry branch supports:

```text
FOUNDRY_RUNTIME=micromamba
FOUNDRY_ENV_PREFIX=/public/home/yinyifan/protein_design/envs/foundry-rfd3
FOUNDRY_CHECKPOINT_DIRS=/public/home/yinyifan/protein_design/weights/foundry
FOUNDRY_RFD3_TIMESTEPS
FOUNDRY_RFD3_BATCH_SIZE
FOUNDRY_RFD3_N_BATCHES
```

All backends normalize to:

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
```

## Three-Way Backend Comparison

Run:

```bash
BACKENDS="rfdiffusion_v1 rfdiffusion_all_atom_legacy foundry_rfd3" \
NUM_DESIGNS=10 NUM_SEQ=4 PREDICT_MAX_RECORDS=1 \
FOUNDRY_RFD3_TIMESTEPS=50 FOUNDRY_RFD3_BATCH_SIZE=2 \
  bash scripts/slurm_templates/submit_backbone_backend_comparison.sh
```

Run root:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554
```

Initial jobs:

```text
rfdiffusion_v1:              GEN 123269, MPNN 123270, AF3 123271, FILTER 123272, MERGE 123273
rfdiffusion_all_atom_legacy: GEN 123274, MPNN 123275, AF3 123276, FILTER 123277, MERGE 123278
foundry_rfd3:                GEN 123279, MPNN 123280, AF3 123281, FILTER 123282, MERGE 123283
comparison:                  123284
```

Retries:

```text
foundry_rfd3 AF3 tasks 3, 4, and 10 retried after transient JAX/CUDA no-visible-GPU failures: PRED 123339, FILTER 123340, MERGE 123341
rfdiffusion_all_atom_legacy AF3 task 6 retried after the same transient JAX/CUDA symptom: PRED 123373, FILTER 123374, MERGE 123375
final comparison retry: 123376
```

Final comparison:

| backend | backbone success | ProteinMPNN success | AF3 success | filter PASS rate | mean pLDDT | mean PAE | mean motif RMSD | mean clash_count | top design |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: | --- |
| rfdiffusion_v1 | 1.00 | 1.00 | 1.00 | 0.90 | 83.11 | 4.81 | 1.93 | 0.10 | design_9 PASS |
| rfdiffusion_all_atom_legacy | 1.00 | 1.00 | 1.00 | 0.00 | 88.85 | 7.05 | 6.57 | 0.00 | design_8 FAIL |
| foundry_rfd3 | 1.00 | 1.00 | 1.00 | 0.40 | 78.89 | 6.13 | 3.12 | 0.00 | design_3 FAIL |

Saved outputs:

```text
examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/reports/backend_comparison.csv
examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/reports/backend_comparison.md
examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/reports/run_report.json
per-backend reports/all_filter_summary.csv
per-backend reports/top_designs.csv
per-backend run_params.json, job_ids.env, logs/
```

Notes:

```text
RFDiffusionAA legacy generation produced 10 PDBs, but idealize_backbone.py fell back to unidealized structures because the ligand-free 5TPN motif input triggered: "Found >1 ligand: []".
Foundry RFD3 is usable as an experimental backbone-generation backend, but RFdiffusion v1 remains the stable baseline for production epitope scaffolding.
```
