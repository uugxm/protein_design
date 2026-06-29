# Final Candidate Selection Policy

Candidate packaging happens after filtering, cross-model prediction review,
fold/sequence diversity selection, and pre-order QC.

## Evidence Hierarchy

Current production policy:

1. AF3 primary pass.
2. RF3 confirmation for high-priority candidates.
3. Motif RMSD and motif atom coverage.
4. PAE/confidence and clash checks.
5. Fold, motif-local, and sequence diversity.
6. Boltz warning state, not a hard fail in no-MSA mode.
7. Sequence and expression pre-order QC.

## Candidate States

- `generated`: backbone exists but downstream validation is incomplete.
- `predicted`: at least one predictor completed.
- `validated_computational`: passes motif/confidence/clash and cross-model
  checks.
- `experimental_candidate`: suitable for wet review.
- `cloning_ready`: only after expression system, vector, tag/fusion, linker,
  codon, and cloning policy are specified.

Runtime final-candidate PDB/CIF/FASTA/QC packages are not tracked in git.
