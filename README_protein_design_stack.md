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
3. AF3 primary prediction, with RF3/Boltz optional cross-validation for AF3 top candidates.
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
retrying. On TYL Slurm the helper parses `sacct --format=JobID,State`, because
`JobIDRaw` is the internal numeric job id and does not retain the array index.

## Backbone Backend Comparison

RFdiffusion v1 is the stable baseline backend for epitope scaffold work. The
older Baker `rf_diffusion_all_atom` integration is retained as
`rfdiffusion_all_atom_legacy`; it is not Foundry RFD3 and should not be called
RF3/RFD3. The new Foundry generation backend is `foundry_rfd3`; it passed smoke
testing and a small 5TPN comparison, but remains experimental pending broader
benchmarking. Foundry `foundry_rf3` is a folding / prediction backend, not a
backbone generator.

Unified backbone launcher:

```bash
cd ~/protein_design/examples/epitope_scaffold
BACKBONE_BACKEND=rfdiffusion_v1 NUM_DESIGNS=1 \
  RUN_ROOT=$PWD/v1_smoke \
  sbatch ../../scripts/slurm_templates/run_backbone_generation.sbatch

BACKBONE_BACKEND=rfdiffusion_all_atom_legacy NUM_DESIGNS=1 \
  RUN_ROOT=$PWD/rfdiffusion_aa_legacy_smoke \
  sbatch ../../scripts/slurm_templates/run_backbone_generation.sbatch

BACKBONE_BACKEND=foundry_rfd3 NUM_DESIGNS=1 \
  RUN_ROOT=$PWD/foundry_rfd3_smoke \
  sbatch ../../scripts/slurm_templates/run_backbone_generation.sbatch
```

All backends normalize outputs to:

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
```

Formal backend comparison:

```bash
cd ~/protein_design
BACKENDS="rfdiffusion_v1 rfdiffusion_all_atom_legacy foundry_rfd3" \
NUM_DESIGNS=10 NUM_SEQ=4 PREDICT_MAX_RECORDS=1 \
FOUNDRY_RFD3_TIMESTEPS=50 FOUNDRY_RFD3_BATCH_SIZE=2 \
  bash scripts/slurm_templates/submit_backbone_backend_comparison.sh
```

The comparison runs all selected backends through the same ProteinMPNN
fixed-position design, AF3 prediction, filter, and merge/ranking pipeline. It
writes:

```text
reports/backend_comparison.csv
reports/backend_comparison.md
```

The 5TPN comparison run saved in
`examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/`
completed with 10/10 backbones, 10/10 ProteinMPNN tasks, and 10/10 AF3
predictions for all three backends after targeted AF3 retries. RFdiffusion v1
passed 9/10 filters; `rfdiffusion_all_atom_legacy` passed 0/10 in this
ligand-free motif test because motif RMSD stayed above threshold; `foundry_rfd3`
passed 4/10. Keep RFdiffusion v1 as the stable baseline for production epitope
scaffolding, and use Foundry RFD3 for side-by-side experimental comparisons.

The RFDiffusionAA smoke-test artifact bundle is saved in
`examples/epitope_scaffold/rfdiffusion_aa_legacy_smoke_5tpn_20260628/`. See
`docs/rfdiffusion_aa_legacy_backend_report.md` for legacy all-atom provenance and
`docs/foundry_rfd3_backend_report.md` for the true Foundry RFD3 integration.

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

### Prediction Backend Decoupling

AF3 is the primary prediction backend. Foundry RF3 and Boltz are optional
cross-validation backends for AF3 top candidates only.

Do not use AF3 `*_data.json` as a cross-model common format. AF3 Stage 1
`*_data.json` files are AF3-internal assets for AF3 Stage 2
`--run_data_pipeline=False`. RF3 and Boltz inputs are generated from the
canonical prediction layer plus optional extracted MSA/template assets.

Canonical input layer:

```bash
python scripts/make_canonical_prediction_inputs.py \
  --fasta array_work/design_9/mpnn_outputs/seqs/design_9.fa \
  --out_dir prediction_inputs/canonical \
  --design_id design_9 \
  --reference_pdb examples/epitope_scaffold/input/5TPN.pdb \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --backbone_pdb rfdiffusion_outputs/design_9.pdb \
  --skip_first --sort_by_score --max_records 1
```

AF3 two-stage templates:

```bash
CANONICAL_MANIFEST=/path/to/canonical_manifest.tsv \
  sbatch scripts/slurm_templates/run_af3_stage1.sbatch

AF3_DATA_INPUT_DIR=/path/to/af3_stage1/raw_stage1 \
  sbatch scripts/slurm_templates/run_af3_inference.sbatch
```

Optional RF3/Boltz cross-validation templates:

```bash
CANONICAL_MANIFEST=/path/to/canonical_manifest.tsv \
  sbatch scripts/slurm_templates/run_rf3_predict.sbatch

CANONICAL_MANIFEST=/path/to/canonical_manifest.tsv \
  sbatch scripts/slurm_templates/run_boltz_predict.sbatch
```

Current top-3 cross-validation artifact:

```text
examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/
```

AF3 primary predictions passed for `design_9`, `design_1`, and `design_4`.
Foundry RF3 is installed, produced structures for all top-3 candidates, and
passes motif RMSD after sequence-derived motif mapping. Boltz is installed and
its cache is populated under `weights/boltz`; Boltz smoke and top-3 prediction
now complete on RTX3090. In the current no-MSA single-sequence top-3 run, Boltz
produces structures for all candidates but flags all three as model conflicts
because pLDDT is below threshold and motif RMSD is very large. Use
`reports/top_consensus_designs.csv` for AF3+RF3 recommendation ranking; Boltz is
an optional warning signal, not a hard gate, until MSA/template-enabled Boltz
validation is tested.
Details are in `docs/cross_model_prediction_report.md`.

Fold/diversity selection is a separate downstream step after filtering and
consensus ranking:

```bash
python scripts/cluster_fold_diversity.py \
  --summary_csv examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/consensus_summary.csv \
  --pdb_dir examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1 \
  --reference_pdb examples/epitope_scaffold/input/5TPN.pdb \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --out_dir examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/fold_clustering \
  --predictor consensus
```

It clusters passing candidates by global fold, motif-local geometry, and
sequence diversity, then writes `reports/fold_clustering/diverse_shortlist.csv`.
Details are in `docs/fold_clustering_report.md`.

Final expression-ready 5TPN candidate packages are under:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/
```

The final shortlist is
`examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/final_expression_shortlist.csv`.
RF3 backup validation for AF3-only diverse candidates is under
`examples/epitope_scaffold/rf3_backup_validation_5tpn_20260629/`.
Details are in `docs/final_candidate_selection_report.md`.

Pre-order QC, run before any cloning-ready order sheet is prepared, is under:

```text
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_sequence_qc.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_structure_qc.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/pre_order_qc_decision.csv
examples/epitope_scaffold/final_candidates_5tpn_20260629/reports/cloning_ready_constructs.csv
```

Details are in `docs/pre_order_qc_report.md`.

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
| RFDiffusionAA legacy / Foundry RFD3 | separate containers or envs; do not mix with RFdiffusion v1 |
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
