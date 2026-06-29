# 5TPN Epitope Scaffold End-to-End Test

Run location on TYL:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/e2e_20260628_180440
```

This is a one-design smoke test of the closed loop:

```text
RFdiffusion motif scaffold -> ProteinMPNN fixed-position design -> AF3 query-only prediction -> motif RMSD / confidence / clash filtering
```

## Slurm Jobs

```text
RFdiffusion: 123129 COMPLETED, 00:01:34, gpu14
ProteinMPNN: 123130_1 COMPLETED, 00:00:08, gpu14
AF3 first attempt: 123131_1 FAILED, 00:00:08, missing container bind for /public/shared/alphafold3/models
AF3 retry: 123133_1 COMPLETED, 00:01:14, gpu14
Filter: 123134_1 COMPLETED, 00:00:02, gpu14
```

The first AF3 attempt is retained in `logs/` as a useful failure record. The
template was fixed by explicitly binding `/public/shared/alphafold3`.

## Key Outputs

- RFdiffusion backbone: `rfdiffusion_outputs/design_0.pdb`
- RFdiffusion mapping: `rfdiffusion_outputs/design_0.trb`
- ProteinMPNN FASTA: `array_work/design_0/mpnn_outputs/seqs/design_0.fa`
- AF3 input JSON: `array_work/design_0/prediction_inputs/af3/design_0_T_0.1.json`
- AF3 confidence JSON: `array_work/design_0/predictions_flat/design_0.json`
- AF3 converted PDB: `array_work/design_0/predictions_flat/design_0.pdb`
- Filter summary: `array_work/design_0/filter_summary.csv`
- Slurm logs: `logs/`

## Filter Summary

```text
design_id: design_0
plddt_mean: 82.34062381852551
pae_mean: 5.001297577854671
motif_rmsd: 1.8237526412014622
motif_atoms_compared: 76
motif_atoms_missing: 0
clash_count: 0
pass: PASS
```
