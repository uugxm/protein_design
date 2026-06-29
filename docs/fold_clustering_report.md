# Fold Clustering And Diversity Selection

Fold clustering is a downstream selection step after AF3 primary filtering and
RF3 confirmation. It prevents the experimental shortlist from being dominated
by many near-duplicate designs.

Use:

```bash
python scripts/cluster_fold_diversity.py \
  --summary_csv /path/to/reports/all_filter_summary.csv \
  --pdb_dir /path/to/predictions_flat \
  --reference_pdb /path/to/reference.pdb \
  --motif_tsv /path/to/motif_residues.tsv \
  --out_dir /path/to/reports/fold_clustering \
  --predictor consensus
```

## Cluster Types

- Global fold clustering compares whole-scaffold topology, preferably with
  US-align or TM-align.
- Motif-local clustering compares the motif and nearby scaffold support shell.
  This matters more for epitope display than global topology alone.
- Sequence clustering keeps the shortlist from overrepresenting one MPNN family.

## Selection Policy

Prioritize designs that pass AF3 and RF3, preserve the motif with low RMSD, have
high confidence and acceptable PAE/clash metrics, and occupy different global,
motif-local, or sequence clusters.

Boltz no-MSA disagreement should be carried as a warning unless MSA/template
enabled Boltz validation has been tested for the task.

Runtime clustering CSVs and PDBs are not tracked in git.
