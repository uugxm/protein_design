# Epitope Scaffold Minimal Example

Purpose: scaffold a fixed epitope/motif into a new protein backbone.

Example motif: RFdiffusion's RSV-F motif example from `5TPN.pdb`, residues `A163-181`.

Prepare input on cluster:

```bash
mkdir -p ~/protein_design/examples/epitope_scaffold/input
ln -sfn ~/protein_design/repos/RFdiffusion/examples/input_pdbs/5TPN.pdb \
  ~/protein_design/examples/epitope_scaffold/input/5TPN.pdb
```

Run RFdiffusion:

```bash
cd ~/protein_design/examples/epitope_scaffold
CONTIGS='[10-40/A163-181/10-40]' NUM_DESIGNS=1 \
  sbatch ../../scripts/slurm_templates/run_rfdiffusion_epitope.sbatch
```

Run ProteinMPNN after RFdiffusion creates backbone PDBs:

```bash
mkdir -p backbones
# copy or symlink RFdiffusion PDBs into backbones/
PDB_DIR=$PWD/backbones OUT_DIR=$PWD/mpnn_outputs NUM_SEQ=4 \
  sbatch ../../scripts/slurm_templates/run_proteinmpnn.sbatch
```

Filter prediction outputs:

```bash
python ../../scripts/filter_designs.py \
  --input_dir predictions \
  --output_csv filter_summary.csv
```

Required interpretation: pass designs only if the motif aligns back to the input motif with acceptable RMSD and remains exposed as intended.
