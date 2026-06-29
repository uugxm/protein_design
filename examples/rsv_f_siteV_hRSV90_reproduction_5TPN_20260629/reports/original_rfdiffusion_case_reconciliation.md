# Original RFdiffusion Case Reconciliation

## Sources checked

- RCSB 5TPN PDB/mmCIF downloaded from `https://files.rcsb.org/download/5TPN.pdb` and `https://files.rcsb.org/download/5TPN.cif`.
- RosettaCommons RFdiffusion repository `https://github.com/RosettaCommons/RFdiffusion.git`, local reference commit `2d0c003df46b9db41d119321f15403dec3716cd9`.
- RFdiffusion official example files:
  - `examples/design_motifscaffolding.sh`
  - `examples/design_motifscaffolding_inpaintseq.sh`
  - `README.md` Docker motif-scaffolding example

## Recovered original example definition

- PDB: `5TPN`
- Motif: chain `A`, residues `163-181` inclusive
- Contig: `[10-40/A163-181/10-40]`
- Motif type: continuous motif segment
- Antibody context: not included in the RFdiffusion command; the input is the 5TPN RSV F structure and the contig selects antigen chain A residues.
- Inpaint-seq variant: `A163-168/A170-171/A179` is masked in the RFdiffusion inpaint-seq example.

## 5TPN structure reconciliation

- Actual PDB chains in the RCSB file are `A/H/L`.
- Chain `A` is a Fusion glycoprotein F0/Fibritin engineered construct.
- Chain `H` is hRSV90 heavy chain.
- Chain `L` is hRSV90 light chain.
- Chain `A` has RSV F residues mapped to UniProt `P03420` over PDB residues `27-513`.
- Chain `A` has fibritin foldon mapped to UniProt `Q38650` over PDB residues `518-544`.
- Chain `A` includes engineered mutations and sequence differences recorded by RCSB, including `N67I`, `S215P`, `I379V`, and `M447V` in the mmCIF entity metadata.
- RCSB missing-residue records include antigen residues `A128-A133` and tag residues `A545-A558`; these are outside the benchmark motif.

## Contact-derived epitope comparison

Contact extraction was performed from the antigen-antibody complex before choosing the benchmark motif.

- 4.0 Angstrom contact set: 16 antigen residues, discontinuous.
- 5.0 Angstrom contact set: 21 antigen residues, discontinuous.
- The contact-derived core overlaps the RFdiffusion motif at `A169-A178`.
- Additional contact-derived distal residues include `A188`, `A191`, `A194`, `A196-A197`, `A200-A201`, `A226`, and `A262-A263`, plus `A271` in the 5.0 Angstrom set.

## Decision for this benchmark

Use `inputs/motif_residues_benchmark.tsv`, the RFdiffusion official continuous `A163-181` motif, for the backend reproduction comparison. This is not copied from the previous 5TPN smoke run: it is recorded here as the official RFdiffusion example motif after independent 5TPN chain/contact extraction and validation.

Reason: the core benchmark question is whether Foundry RFD3 can reproduce the RFdiffusion original motif-scaffolding case faster or better under the same motif input. The contact-derived sets remain required provenance and QC context, but they are discontinuous and not identical to the published/example continuous RFdiffusion task.
