# Epitope Scaffold Minimal Closed Loop

Purpose: scaffold a fixed epitope/motif into a new protein backbone, keep the
motif sequence fixed during ProteinMPNN design, predict designed structures, and
summarize motif RMSD / confidence / clash metrics.

Example motif: RFdiffusion's RSV-F motif example from `5TPN.pdb`, residues
`A163-181`.

## 0. Prepare input on TYL

```bash
mkdir -p ~/protein_design/examples/epitope_scaffold/input
ln -sfn ~/protein_design/repos/RFdiffusion/examples/input_pdbs/5TPN.pdb \
  ~/protein_design/examples/epitope_scaffold/input/5TPN.pdb
```

## 1. RFdiffusion motif scaffolding

```bash
cd ~/protein_design/examples/epitope_scaffold
CONTIGS='[10-40/A163-181/10-40]' \
NUM_DESIGNS=4 \
OUTPUT_PREFIX=$PWD/rfdiffusion_outputs/design \
  sbatch ../../scripts/slurm_templates/run_rfdiffusion_epitope.sbatch
```

RFdiffusion writes paired `.pdb` and `.trb` files. The `.trb` files are used
below to map original motif residues to the output scaffold numbering.

Create the array task list after RFdiffusion finishes:

```bash
find "$PWD/rfdiffusion_outputs" -maxdepth 1 -name '*.pdb' | sort > backbone_list.txt
wc -l backbone_list.txt
```

## 2. ProteinMPNN fixed-position design

For one small batch:

```bash
cd ~/protein_design/examples/epitope_scaffold
PDB_DIR=$PWD/rfdiffusion_outputs \
TRB_DIR=$PWD/rfdiffusion_outputs \
MOTIF_TSV=$PWD/motif_residues.tsv \
OUT_DIR=$PWD/mpnn_outputs \
NUM_SEQ=4 \
  sbatch ../../scripts/slurm_templates/run_proteinmpnn.sbatch
```

For array execution, use the number printed by `wc -l backbone_list.txt`:

```bash
cd ~/protein_design/examples/epitope_scaffold
TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
MOTIF_TSV=$PWD/motif_residues.tsv \
STAGE=mpnn \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

The fixed-position file is generated as
`mpnn_outputs/fixed_positions.jsonl` or per-array-task
`array_work/<design_id>/mpnn_outputs/fixed_positions.jsonl`.

Manual fixed-position generation:

```bash
python ../../scripts/make_fixed_positions_jsonl.py \
  --pdb_dir rfdiffusion_outputs \
  --trb_dir rfdiffusion_outputs \
  --motif_tsv motif_residues.tsv \
  --output_jsonl mpnn_outputs/fixed_positions.jsonl \
  --strict
```

## 3. AF3 / AF2 / Boltz prediction

Run AF3 prediction through the array template:

```bash
cd ~/protein_design/examples/epitope_scaffold
TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
MOTIF_TSV=$PWD/motif_residues.tsv \
STAGE=predict \
PREDICTOR=af3 \
PREDICT_MAX_RECORDS=1 \
PREDICT_SKIP_FIRST=1 \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

The template uses the TYL AF3 3.0.1 container and explicit bind path recorded in
GBrain:

```text
AF3_SIF=/public/apps/alphafold3/alphafold3/alphafold3.0.1.sif
AF3_MODEL_DIR=/public/shared/alphafold3/models
AF3_DB_DIR=/public/shared/alphafold3
AF3_BIND=/public/shared/alphafold3:/public/shared/alphafold3
AF3_EXTRA_ARGS=--run_data_pipeline=False
```

ProteinMPNN FASTA records are converted automatically into AF3 query-only JSON
under `array_work/<design_id>/prediction_inputs/af3/`. AF3 output is collected
into flat files under `array_work/<design_id>/predictions_flat/`.

Boltz input preparation is wired through `PREDICTOR=boltz`; when no MSA is
available, the adapter writes `msa: empty` for Boltz single-sequence mode.
Current TYL status: the Boltz environment exists, but GPU jobs cannot download
the Boltz cache because compute nodes have no outbound network. Populate
`~/protein_design/weights/boltz` offline before rerunning Boltz prediction.

## 4. Motif RMSD / confidence / clash filtering

```bash
TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
MOTIF_TSV=$PWD/motif_residues.tsv \
STAGE=filter \
MIN_PLDDT=70 \
MAX_PAE=10 \
MAX_MOTIF_RMSD=1.5 \
MAX_CLASHES=20 \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

Required interpretation: pass designs only if the motif aligns back to the input
motif with acceptable RMSD and the predicted scaffold has acceptable confidence
and clash metrics.

See `e2e_5tpn_20260628/` for a completed one-design RFdiffusion -> ProteinMPNN
-> AF3 -> filter test with logs and output artifacts.
