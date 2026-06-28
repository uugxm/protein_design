# 5TPN Batch Stability Test

Run location on TYL:

```text
/public/home/yinyifan/protein_design/examples/epitope_scaffold/batch_stability_20260628_182526
```

Batch parameters:

```text
RFdiffusion backbones: 10
ProteinMPNN sequences per backbone: 4
AF3 predictions per backbone: top 1 by ProteinMPNN score
Filter thresholds: pLDDT >= 70, PAE <= 10, motif RMSD <= 2.5 A, clash_count <= 20
```

The workflow used Slurm dependencies and arrays:

```text
RFdiffusion GPU job -> MPNN GPU array -> AF3 GPU array -> CPU filter array -> CPU merge
```

The original GPU filter array was cancelled before running and replaced with a
CPU filter array, because filtering does not need GPU resources.

## Job IDs

```text
RF_JOB=123135
MPNN_JOB=123136
PRED_JOB=123137
FILT_JOB=123138       # cancelled before running
MERGE_JOB=123139      # cancelled before running
FILT2_JOB=123158      # superseded because dependency used afterok on a partially failed AF3 array
MERGE2_JOB=123159     # superseded
PRED_RETRY_JOB=123160 # retry design_5 only
FILT3_JOB=123161      # CPU filter array
MERGE3_JOB=123162     # CPU merge
```

## Stability Summary

```text
RFdiffusion outputs: 10 / 10
ProteinMPNN FASTA outputs: 10 / 10
AF3 first pass: 9 / 10 completed, 1 / 10 failed
AF3 retry: 1 / 1 completed
Final prediction outputs: 10 / 10
Filter summaries: 10 / 10
PASS rows: 9 / 10
FAIL rows: 1 / 10
```

The first-pass AF3 failure was `123137_6` on `gpu15`: the job had an allocated
GPU visible to `nvidia-smi`, but JAX inside the container reported no visible
CUDA device. A targeted retry, `123160_6`, completed on `gpu14`.

## Top Designs

Top sorting order:

```text
pLDDT descending, PAE ascending, motif RMSD ascending, clash_count ascending
```

Top row from `reports/top_designs.csv`:

```text
design_0: pLDDT=89.8871, PAE=2.9344, motif_RMSD=0.9535, clash_count=0, PASS
```

Canonical summary files:

- `reports/all_filter_summary.csv`
- `reports/top_designs.csv`
- `reports/run_report.json`
- `reports/batch_stability_summary.json`
- `reports/job_accounting.tsv`
