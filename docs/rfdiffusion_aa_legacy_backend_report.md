# Legacy RFDiffusionAA Backend Report

Date: 2026-06-28

## Naming Decision

This report covers the old `baker-laboratory/rf_diffusion_all_atom` integration.
That upstream README names the code "RFDiffusion AA". It is not the Foundry
RFD3/RFdiffusion3 backend and must not be called RF3 or RFD3 in this stack.

This stack therefore uses the backend name:

```text
rfdiffusion_all_atom_legacy
```

`BACKBONE_BACKEND=rf3` is no longer accepted for this backend. RF3 in Foundry is
a folding / prediction model, not this legacy backbone generator. The true
Foundry generation backend is `foundry_rfd3`; see
`docs/foundry_rfd3_backend_report.md`.

## Upstream Source

```text
Repository: https://github.com/baker-laboratory/rf_diffusion_all_atom.git
Installed local path: /public/home/yinyifan/protein_design/repos/rf_diffusion_all_atom
Installed commit: f913a19e16f30858ce7a724fe028475b1871319c
Upstream main HEAD checked: f913a19e16f30858ce7a724fe028475b1871319c
Submodule: lib/rf2aa -> https://github.com/baker-laboratory/RoseTTAFold-All-Atom.git
Submodule commit: f87f5b8cdf1a68a7d4fa8c44300197944698a995
```

The upstream README install instructions require:

```text
Container: http://files.ipd.uw.edu/pub/RF-All-Atom/containers/rf_se3_diffusion.sif
Weights: http://files.ipd.uw.edu/pub/RF-All-Atom/weights/RFDiffusionAA_paper_weights.pt
Runtime: Apptainer/Singularity with --nv for GPU runs
Entry point: run_inference.py through the container
```

## License

The repository contains a BSD License:

```text
Copyright (c) 2024 University of Washington.
Developed at the Institute for Protein Design by Rohith Krishna and Woody Ahern.
The license covers both the source code and model weights referenced for download
in the README file.
```

## Installed Runtime

```text
Source checkout: ~/protein_design/repos/rf_diffusion_all_atom
Container: ~/protein_design/containers/rf_se3_diffusion.sif
Weights: ~/protein_design/weights/RFDiffusionAA_paper_weights.pt
Environment note: ~/protein_design/envs/rfdiffusion_all_atom_legacy.env
Isolation strategy: Apptainer container; no changes to RFdiffusion v1 conda env
```

The RFdiffusion v1 baseline remains:

```text
~/protein_design/repos/RFdiffusion
~/protein_design/envs/rfdiffusion-se3nv
```

## Interface Contract

The new launcher is:

```text
scripts/slurm_templates/run_backbone_generation.sbatch
```

Supported backend values:

```text
BACKBONE_BACKEND=rfdiffusion_v1
BACKBONE_BACKEND=rfdiffusion_all_atom_legacy
BACKBONE_BACKEND=foundry_rfd3
```

This report documents only the legacy all-atom branch. See
`docs/foundry_rfd3_backend_report.md` for the Foundry branch.

Required normalized outputs:

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
logs/<slurm stdout/stderr>
```

The downstream ProteinMPNN, AF3 prediction, filtering, merge, and ranking stages
are reused unchanged.

## Motif Mapping Adapter

RFDiffusionAA normally writes `.trb` metadata from its contig map, but the
5TPN ligand-free motif smoke test exposed an upstream post-processing issue:
denoising completes and `unidealized/design_N.pdb` is written, then
`idealize_backbone.rewrite` fails because it asserts exactly one ligand.

The stack handles this without modifying upstream source:

```text
LEGACY_AA_ALLOW_UNIDEALIZED_FALLBACK=1
```

When this fallback is enabled, `run_backbone_generation.sbatch` copies
`rfdiffusion_outputs/unidealized/design_N.pdb` to the normalized output path and
runs:

```text
scripts/make_motif_mapping_from_sequence.py
```

That adapter extracts the reference motif sequence from `INPUT_PDB` and
`MOTIF_TSV`, finds the exact motif sequence in the generated PDB, and writes an
NPZ-style `.trb` file with `con_ref_pdb_idx` and `con_hal_pdb_idx`. The existing
`make_fixed_positions_jsonl.py` then uses this mapping unchanged.

For ligand-free motif batches, `run_backbone_generation.sbatch` loops
RFDiffusionAA with `inference.num_designs=1` and increasing
`inference.design_startnum`. This is deliberate: a single upstream
`inference.num_designs=10` call exits after the first ligand-free design because
of the idealization assertion, so looping keeps the batch additive and avoids
patching upstream source.

## Contig Syntax

RFdiffusion v1 uses slash-separated contigs:

```text
[10-40/A163-181/10-40]
```

RFDiffusionAA uses comma-separated contigs inside a Hydra list:

```text
["10-40,A163-181,10-40"]
```

Both represent the same 5TPN motif scaffold intent for motif `A163-181`, but
the syntax must be backend-specific.

## Smoke Test Plan

Minimal 5TPN smoke test:

```bash
cd ~/protein_design/examples/epitope_scaffold/rfdiffusion_aa_legacy_smoke_5tpn
BACKBONE_BACKEND=rfdiffusion_all_atom_legacy NUM_DESIGNS=1 \
  RUN_ROOT=$PWD \
  INPUT_PDB=~/protein_design/examples/epitope_scaffold/input/5TPN.pdb \
  MOTIF_TSV=~/protein_design/examples/epitope_scaffold/motif_residues.tsv \
  sbatch ~/protein_design/scripts/slurm_templates/run_backbone_generation.sbatch
```

Expected checks:

```text
Slurm GPU job completes
rfdiffusion_outputs/design_0.pdb exists
rfdiffusion_outputs/design_0.trb exists
backbone_list.txt contains design_0.pdb
ProteinMPNN parse_multiple_chains.py can parse the output PDB
make_fixed_positions_jsonl.py can use the .trb mapping with --strict
```

## Backend Comparison Plan

Formal comparison launcher:

```bash
cd ~/protein_design
BACKENDS="rfdiffusion_v1 rfdiffusion_all_atom_legacy foundry_rfd3" \
NUM_DESIGNS=10 NUM_SEQ=4 PREDICT_MAX_RECORDS=1 \
  bash scripts/slurm_templates/submit_backbone_backend_comparison.sh
```

The launcher runs:

```text
rfdiffusion_v1 -> ProteinMPNN -> AF3 -> filter -> merge
rfdiffusion_all_atom_legacy -> ProteinMPNN -> AF3 -> filter -> merge
foundry_rfd3 -> ProteinMPNN -> AF3 -> filter -> merge
```

Then writes:

```text
reports/backend_comparison.csv
reports/backend_comparison.md
```

Comparison metrics:

```text
backbone generation success rate
ProteinMPNN success rate
AF3 prediction success rate
filter PASS rate
pLDDT distribution
PAE distribution
motif RMSD distribution
clash_count distribution
top design ranking
```

## Current Status

Source inspection, isolated runtime setup, smoke testing, and a 10-backbone
backend comparison completed on 2026-06-28.

### Runtime Artifact Status

```text
Source checkout: /public/home/yinyifan/protein_design/repos/rf_diffusion_all_atom
Source commit: f913a19e16f30858ce7a724fe028475b1871319c
Submodule commit: f87f5b8cdf1a68a7d4fa8c44300197944698a995
Container: /public/home/yinyifan/protein_design/containers/rf_se3_diffusion.sif
Weights: /public/home/yinyifan/protein_design/weights/RFDiffusionAA_paper_weights.pt
Runtime mode: Apptainer --nv
RFdiffusion v1 env: unchanged
```

### Smoke Test Result

2026-06-28 19:41 CST smoke test:

```text
Run directory: /public/home/yinyifan/protein_design/examples/epitope_scaffold/rfdiffusion_all_atom_legacy_smoke_5tpn_20260628_194145
Slurm job: 123174
Node: gpu14
State: COMPLETED
Elapsed: 00:01:52
Backend: rfdiffusion_all_atom_legacy
Input motif: 5TPN chain A residues 163-181
RFDiffusionAA contig: ["10-40,A163-181,10-40"]
Output PDB: rfdiffusion_outputs/design_0.pdb
Output mapping: rfdiffusion_outputs/design_0.trb
Fallback: upstream ligand-free idealization failed; unidealized PDB was normalized and sequence-derived mapping was generated
```

Validation:

```text
ProteinMPNN parse_multiple_chains.py parsed 1 PDB.
make_fixed_positions_jsonl.py --strict succeeded.
fixed_positions.jsonl: {"design_0": {"A": [38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56]}}
mapping: A163-181 -> A38-56
```

### RFdiffusion v1 vs RFDiffusionAA Comparison

Run directory:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/backend_comparison_20260628_195056
```

Parameters:

```text
Input PDB: 5TPN
Motif: chain A residues 163-181
RFdiffusion v1 backbones: 10
RFDiffusionAA backbones: 10
ProteinMPNN sequences per backbone: 4
AF3 predictions per backbone used for this speed test: top 1
Filter thresholds: min pLDDT 70, max PAE 10, max motif RMSD 2.5 A, max clashes 20
```

Initial AF3 arrays had two transient failures:

```text
rfdiffusion_v1: job 123188_5 FAILED, retried as 123251_5 and completed
rfdiffusion_all_atom_legacy: job 123193_6 FAILED, retried as 123254_6 and completed
Retry helper fix: parse sacct JobID instead of JobIDRaw on TYL Slurm
Final comparison refresh job after compare-script correction: 123258, COMPLETED
```

Final comparison:

| backend | backbone success | MPNN success | AF3 success | filter PASS | pLDDT mean | PAE mean | motif RMSD mean | clash mean | top design | top PASS |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfdiffusion_v1 | 10/10 | 10/10 | 10/10 | 9/10 | 83.6895 | 4.3982 | 1.2157 | 0.1000 | design_3 | PASS |
| rfdiffusion_all_atom_legacy | 10/10 | 10/10 | 10/10 | 0/10 | 88.8509 | 7.0484 | 6.5673 | 0.0000 | design_8 | FAIL |

Interpretation:

```text
The unified backend interface works for both backends, and both backends can feed
the existing ProteinMPNN -> AF3 -> filter/ranking chain. In this small 5TPN
motif test, RFDiffusionAA generated higher pLDDT predictions but failed the
motif RMSD threshold for all 10 designs. Treat RFDiffusionAA as experimental for
ligand-free motif scaffolding until motif-numbering/mapping and contig settings
are further tuned.
```

Local compact result bundle:

```text
examples/epitope_scaffold/rfdiffusion_all_atom_legacy_smoke_5tpn_20260628/
examples/epitope_scaffold/backend_comparison_5tpn_20260628/
```
