# Fold Clustering and Diversity Shortlist Report

Date: 2026-06-29

This step is an independent downstream selection layer after the stable epitope scaffold filtering workflow:

```text
RFdiffusion v1 / Foundry RFD3 -> ProteinMPNN -> AF3 primary prediction -> RF3 optional confirmation -> filtering/ranking -> fold diversity selection
```

It does not replace or modify RFdiffusion v1, ProteinMPNN, AF3, RF3, or Boltz execution. Its purpose is to avoid sending many near-duplicate scaffold topologies to expression when several designs already pass AF3 primary filtering and RF3 confirmation.

## Why Add Clustering After AF3/RF3 Filtering

AF3/RF3 filtering answers whether each individual design plausibly preserves the motif and folds with acceptable confidence. It does not answer whether the final experimental list is diverse. For epitope scaffold work, diversity matters because failures can be scaffold-family specific: a set of highly similar folds may share expression, solubility, aggregation, or motif-presentation liabilities.

The selection layer therefore clusters passing candidates by:

- Global fold similarity: whole-scaffold topology-level redundancy.
- Motif-local geometry: motif plus nearby supporting scaffold geometry, which is more important than global topology for epitope display.
- Sequence identity: sequence-level redundancy among ProteinMPNN designs.

Boltz no-MSA single-sequence disagreement is preserved as a warning only. The previous diagnostic showed that current Boltz no-MSA mode is not reliable as a hard gate for this de novo 5TPN motif scaffold task. Boltz should become a stronger validation signal only after MSA/template-enabled inputs are tested.

## Implementation

New script:

```bash
scripts/cluster_fold_diversity.py
```

Main inputs:

- `--summary_csv`: `reports/all_filter_summary.csv` or `reports/consensus_summary.csv`
- `--pdb_dir`: AF3/RF3 flat-output or batch root directory containing prediction PDBs
- `--reference_pdb`: reference motif PDB
- `--motif_tsv`: motif residue TSV
- `--sequence_fasta`: optional ProteinMPNN FASTA path or directory
- `--predictor`: `af3`, `rf3`, or `consensus`

Main outputs:

- `fold_cluster_summary.csv`
- `motif_local_cluster_summary.csv`
- `sequence_cluster_summary.csv`
- `diverse_shortlist.csv`
- `cluster_report.md`

US-align/TM-align and MMseqs2/CD-HIT were not available in the local PATH used for this report. The current run used Python fallbacks:

- Global fold: pairwise Kabsch C-alpha RMSD converted to an approximate similarity score.
- Motif-local: pairwise Kabsch RMSD over motif-neighborhood backbone atoms.
- Sequence: pairwise sequence identity.

The global fallback is useful for small triage runs, but TM-score from US-align or TM-align should be preferred on the SLURM cluster when available.

## Runs

### Top-3 AF3/RF3 Consensus Candidates

Command:

```bash
python scripts/cluster_fold_diversity.py \
  --summary_csv examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/consensus_summary.csv \
  --pdb_dir examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1 \
  --reference_pdb examples/epitope_scaffold/input/5TPN.pdb \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --out_dir examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/fold_clustering \
  --predictor consensus \
  --min_plddt 70 \
  --max_pae 10 \
  --max_motif_rmsd 2.0 \
  --max_clashes 20 \
  --tm_threshold 0.6 \
  --motif_local_rmsd_threshold 2.0 \
  --seq_identity_threshold 0.8
```

Results:

| metric | value |
| --- | ---: |
| retained designs | 3 |
| global fold clusters | 3 |
| motif-local clusters | 3 |
| sequence clusters | 3 |

Top-3 consensus shortlist:

| rank | design | global | motif-local | sequence | AF3 motif RMSD | RF3 motif RMSD | recommendation |
| ---: | --- | --- | --- | --- | ---: | ---: | --- |
| 1 | design_1 | F1 | M1 | S1 | 0.721 | 0.751 | recommend |
| 2 | design_9 | F3 | M3 | S3 | 1.042 | 1.050 | recommend |
| 3 | design_4 | F2 | M2 | S2 | 1.850 | 1.680 | recommend |

Interpretation:

- `design_1`, `design_9`, and `design_4` are all AF3/RF3 PASS.
- They are separated by global fold, motif-local, and sequence clustering in the current fallback analysis.
- `design_1` and `design_9` should both remain prioritized; they do not appear to be the same scaffold topology or motif-local presentation class in this run.
- `design_4` is RF3-confirmed but has weaker RF3 confidence and higher motif RMSD than `design_1` and `design_9`; keep it as a third diverse consensus candidate rather than the first expression choice.

Output directory:

```text
examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/fold_clustering/
```

### Larger RFdiffusion v1 AF3 Batch

Command:

```bash
python scripts/cluster_fold_diversity.py \
  --summary_csv examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/reports/all_filter_summary.csv \
  --pdb_dir examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1 \
  --reference_pdb examples/epitope_scaffold/input/5TPN.pdb \
  --motif_tsv examples/epitope_scaffold/motif_residues.tsv \
  --sequence_fasta examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/array_work \
  --out_dir examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/reports/fold_clustering \
  --predictor af3 \
  --min_plddt 70 \
  --max_pae 10 \
  --max_motif_rmsd 2.0 \
  --max_clashes 20 \
  --tm_threshold 0.6 \
  --motif_local_rmsd_threshold 2.0 \
  --seq_identity_threshold 0.8
```

Results:

| metric | value |
| --- | ---: |
| retained AF3 PASS designs | 7 |
| global fold clusters | 7 |
| motif-local clusters | 7 |
| sequence clusters | 6 |

AF3-only diverse shortlist:

| rank | design | global | motif-local | sequence | AF3 motif RMSD | recommendation |
| ---: | --- | --- | --- | --- | ---: | --- |
| 1 | design_1 | F2 | M2 | S2 | 0.721 | recommend after RF3 confirmation |
| 2 | design_0 | F1 | M1 | S1 | 0.830 | recommend after RF3 confirmation |
| 3 | design_7 | F6 | M6 | S6 | 0.891 | recommend after RF3 confirmation |
| 4 | design_2 | F3 | M3 | S3 | 0.953 | recommend after RF3 confirmation |
| 5 | design_3 | F4 | M4 | S4 | 1.039 | recommend after RF3 confirmation |
| 6 | design_9 | F7 | M7 | S3 | 1.042 | backup/top10 |
| 7 | design_4 | F5 | M5 | S5 | 1.850 | backup/top10 |

Interpretation:

- The larger batch is AF3-only in this clustering run; use it for diversity planning, not final consensus ranking.
- `design_9` and `design_2` share a sequence cluster at 96.7% identity, but they remain separate global fold and motif-local clusters by the current structural fallback. If expression slots are scarce, do not choose both solely for sequence diversity; if motif-local diversity is prioritized, keeping both is defensible after RF3 confirmation.
- `design_1` and `design_9` are different in both global and motif-local clustering, so they should not be treated as redundant.

Output directory:

```text
examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/reports/fold_clustering/
```

## Experimental Recommendation

For the current RF3-confirmed consensus set, prioritize:

1. `design_1`
2. `design_9`
3. `design_4`

If expanding beyond the RF3-confirmed top-3, the AF3-only diversity batch suggests `design_0`, `design_7`, `design_2`, and `design_3` are structurally diverse follow-up candidates, but they should be RF3-confirmed before being promoted above the existing consensus set.

## Next Operational Notes

- On the SLURM cluster, prefer US-align or TM-align for global fold clustering when available.
- Motif-local clustering should remain the dominant diversity axis for epitope scaffold selection.
- Boltz no-MSA disagreement should continue to be reported as a warning only until MSA/template assets are enabled and validated.
