# Antibody / Nanobody Design Minimal Example

Purpose: support VHH/scFv/CDR design against an antigen epitope without losing antibody-specific numbering/framework constraints.

Inputs:

```text
input/antigen.pdb
epitope residues: A100,A101,A102
format target: VHH or scFv, defined by the selected antibody pipeline
```

Run template:

```bash
cd ~/protein_design/examples/antibody_design
ANTIGEN_PDB=$PWD/input/antigen.pdb EPITOPE=A100,A101,A102 \
  sbatch ../../scripts/slurm_templates/run_rfantibody.sbatch
```

Current deployment state: RFantibody source is cloned, but its isolated runtime environment is not installed yet. Recommended isolated support environment:

- ANARCI or AbNumber for numbering.
- ImmuneBuilder/ABodyBuilder2/NanoBodyBuilder2 for antibody structure modeling.
- Biopython, gemmi, pdb-tools for PDB/FASTA handling.
- PyMOL-open-source or ChimeraX if available for inspection.

Filtering should report CDR boundaries, framework preservation, epitope contacts, developability liabilities, pLDDT/pTM/ipTM when predicted, and clashes/interface geometry.
