# Epitope Scaffold Preflight

- Confirm input PDB or mmCIF provenance and checksum.
- Confirm antigen, antibody heavy, and antibody light chain IDs.
- Record missing residues, mutations, engineered linkers, tags, and chimeric regions.
- Generate contact-derived motif residues before using any literature or example motif.
- Record the exact motif provenance: contact cutoff, curated residue set, or original-paper residue set.
- Confirm RFdiffusion v1 contig and Foundry RFD3 input use the same motif definition.
- Confirm compute jobs will run through Slurm, not on a login node.
