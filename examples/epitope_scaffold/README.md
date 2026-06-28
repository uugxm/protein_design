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

## 3. AF3 / AF2 / Boltz prediction input

Prepare AF3 JSON jobs from ProteinMPNN FASTA output:

```bash
mkdir -p af3_inputs
python ../../scripts/make_af3_json_inputs.py \
  --fasta mpnn_outputs/seqs/design.fa \
  --out_dir af3_inputs
```

Run prediction with the available site interface. Do not download or overwrite
AF3 databases or model weights:

```bash
apptainer exec ~/protein_design/containers/alphafold3.sif \
  python /app/alphafold/run_alphafold.py \
    --input_dir "$PWD/af3_inputs" \
    --output_dir "$PWD/predictions" \
    --model_dir /public/home/yinyifan/models \
    --db_dir /public/home/yinyifan/public_databases
```

If using ColabFold/AF2 or Boltz later, place predicted PDB/CIF and JSON
confidence files under `predictions/` before running the same filter step.

## 4. Motif RMSD / confidence / clash filtering

```bash
python ../../scripts/filter_designs.py \
  --input_dir predictions \
  --pdb_dir predictions \
  --reference_pdb input/5TPN.pdb \
  --motif_tsv motif_residues.tsv \
  --trb_dir rfdiffusion_outputs \
  --min_plddt 70 \
  --max_pae 10 \
  --max_motif_rmsd 1.5 \
  --max_clashes 20 \
  --output_csv filter_summary.csv
```

Required interpretation: pass designs only if the motif aligns back to the input
motif with acceptable RMSD and the predicted scaffold has acceptable confidence
and clash metrics.
