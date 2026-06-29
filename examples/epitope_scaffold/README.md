# Epitope Scaffold Minimal Template

This directory contains reusable input templates only. It intentionally does not
track benchmark PDBs, generated backbones, ProteinMPNN outputs, predictions,
logs, or final candidate packages.

## Required User Inputs

For a real run, provide:

- `INPUT_PDB`: reference PDB/CIF containing the motif residues.
- `MOTIF_TSV`: motif definition TSV with `chain/start/end` or one residue per
  row.
- `CONTIGS`: RFdiffusion v1 contig string for continuous motifs, or a Foundry
  RFD3 input generated from `scripts/make_rfd3_motif_input.py`.

You can prepare a motif from a complex with:

```bash
python ../../scripts/prepare_epitope_from_complex.py \
  --complex_pdb /path/to/complex.pdb \
  --motif_ranges A10-25 \
  --out_dir input_prepared \
  --copy_reference

python ../../scripts/validate_motif_definition.py \
  --reference_pdb input_prepared/reference.pdb \
  --motif_tsv input_prepared/motif_residues.tsv \
  --out_json input_prepared/motif_validation.json \
  --normalized_tsv input_prepared/motif_residues.normalized.tsv
```

## RFdiffusion V1 Backbone Generation

```bash
cd ~/protein_design/examples/epitope_scaffold
INPUT_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
CONTIGS='[10-40/A10-25/10-40]' \
NUM_DESIGNS=4 \
OUTPUT_PREFIX=$PWD/rfdiffusion_outputs/design \
  sbatch ../../scripts/slurm_templates/run_rfdiffusion_epitope.sbatch
```

Create the array task list after RFdiffusion finishes:

```bash
find "$PWD/rfdiffusion_outputs" -maxdepth 1 -name '*.pdb' | sort > backbone_list.txt
```

## Foundry RFD3 Backbone Generation

```bash
INPUT_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
BACKBONE_BACKEND=foundry_rfd3 \
FOUNDRY_RFD3_FIXED_ATOMS=ALL \
RUN_ROOT=$PWD/rfd3_run \
NUM_DESIGNS=4 \
  sbatch ../../scripts/slurm_templates/run_backbone_generation.sbatch
```

## ProteinMPNN Fixed-Position Design

```bash
PDB_DIR=$PWD/rfdiffusion_outputs \
TRB_DIR=$PWD/rfdiffusion_outputs \
MOTIF_TSV=/path/to/motif_residues.tsv \
OUT_DIR=$PWD/mpnn_outputs \
NUM_SEQ=4 \
  sbatch ../../scripts/slurm_templates/run_proteinmpnn.sbatch
```

For array execution:

```bash
TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
REFERENCE_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=mpnn \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

## Prediction And Filtering

AF3 is the primary predictor. RF3 and Boltz are optional cross-validation
backends for top AF3 candidates.

```bash
TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
REFERENCE_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=predict \
PREDICTOR=af3 \
PREDICT_MAX_RECORDS=1 \
PREDICT_SKIP_FIRST=1 \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch

TASK_LIST=$PWD/backbone_list.txt \
WORK_ROOT=$PWD/array_work \
REFERENCE_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=filter \
MIN_PLDDT=70 \
MAX_PAE=10 \
MAX_MOTIF_RMSD=1.5 \
MAX_CLASHES=20 \
  sbatch --array=1-4 ../../scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

Do not track the produced `rfdiffusion_outputs/`, `mpnn_outputs/`,
`prediction_inputs/`, `predictions/`, `predictions_flat/`, `array_work/`, or
`logs/` directories.
