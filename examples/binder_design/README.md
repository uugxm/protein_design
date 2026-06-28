# Binder Design Minimal Example

Purpose: design a new protein binder against a target chain and hotspot residues.

Binder design is not epitope scaffolding. Here the designed protein binds a target surface; it does not primarily display a pre-existing epitope on a scaffold.

Inputs:

```text
input/target.pdb
target chain: A
hotspots: A45,A46,A47
```

Run template:

```bash
cd ~/protein_design/examples/binder_design
TARGET_PDB=$PWD/input/target.pdb TARGET_CHAIN=A HOTSPOTS=A45,A46,A47 \
  sbatch ../../scripts/slurm_templates/run_bindcraft.sbatch
```

Current deployment state: BindCraft source is cloned, but its isolated runtime environment is not installed yet. Once installed, the intended workflow is:

1. Generate binder backbones against `target.pdb` and hotspots.
2. Run ProteinMPNN on binder backbones.
3. Predict binder-target complexes with AF2/AF3/Boltz.
4. Filter by pLDDT, pTM/ipTM, PAE/interface PAE, clashes, buried surface/contact count, and target-hotspot contact recovery.
