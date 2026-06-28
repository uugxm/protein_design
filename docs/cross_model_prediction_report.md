# Cross-Model Prediction Backend Report

Date: 2026-06-28

Scope: AF3 remains the primary prediction backend. Foundry RF3 and Boltz are
optional cross-validation backends that run only on AF3 top candidates.

## Boundary

AF3 `*_data.json` is not a cross-model interchange format.

- AF3 Stage 1 writes AF3-internal `*_data.json`.
- AF3 Stage 2 may consume those files with `--run_data_pipeline=False`.
- RF3 and Boltz inputs are generated from canonical prediction inputs plus
  optional extracted MSA/template assets.
- RF3/Boltz adapters do not read AF3 internal data JSON.

## Runtime State

Foundry RF3:

- env: `/public/home/yinyifan/protein_design/envs/foundry-rfd3`
- repo: `/public/home/yinyifan/protein_design/repos/foundry`
- checkpoint: `/public/home/yinyifan/protein_design/weights/foundry/rf3_foundry_01_24_latest_remapped.ckpt`
- size: `3038876446` bytes
- sha256: `364ef592fd8042a9cf4176d045015190f8322f961ccca38d891b20ca578d3bb0`
- install command:
  `FOUNDRY_CHECKPOINT_DIRS=/public/home/yinyifan/protein_design/weights/foundry foundry install rf3 --checkpoint-dir /public/home/yinyifan/protein_design/weights/foundry`
- registry: `foundry list-installed` recognizes the RF3 checkpoint.

Boltz:

- env: `/public/home/yinyifan/protein_design/envs/boltz`
- repo: `/public/home/yinyifan/protein_design/repos/boltz`
- package: `boltz 2.2.1`
- Python: `3.11.15`
- PyTorch: `2.6.0+cu124`
- install command:
  `/public/apps/miniconda/24.4.0/bin/conda create -p .../envs/boltz python=3.11 pip`;
  `pip install --index-url https://download.pytorch.org/whl/cu124 torch==2.6.0`;
  `pip install -e /public/home/yinyifan/protein_design/repos/boltz`
- cache path: `/public/home/yinyifan/protein_design/weights/boltz`
- cache status: not populated. GPU compute nodes cannot reach the Boltz
  download URLs, and login-node prefetch did not create `mols.tar`.

## Templates

RF3 prediction uses only the RF3 folding entrypoint:

```bash
rf3 fold inputs=<rf3_input_json_or_dir> out_dir=<out_dir> ckpt_path=<checkpoint>
```

`scripts/slurm_templates/run_rf3_predict.sbatch` rejects RFD3 design overrides
such as `diffusion_batch_size`, `n_batches`, and
`inference_sampler.num_timesteps`.

Boltz prediction uses native Boltz YAML inputs:

```bash
boltz predict prediction_inputs/boltz --out_dir predictions_boltz --cache /public/home/yinyifan/protein_design/weights/boltz
```

If no MSA is available, `scripts/make_boltz_inputs.py` writes `msa: empty`,
which is Boltz's documented single-sequence mode.

## Smoke Tests

RF3 smoke:

- job: `123384`
- input: `models/rf3/tests/data/5vht_from_json.json`
- status: COMPLETED, `00:01:15`, exit `0:0`
- GPU check: `torch.cuda.is_available=True`, RTX3090
- output: `examples/epitope_scaffold/rf3_smoke_5vht_20260628/rf3_predictions/5vht_from_json/5vht_from_json_model.cif`
- confidence: `5vht_from_json_summary_confidences.json`
- pTM: `0.9055707454681396`, above the README expectation of `>0.8`
- collector: generated flat CIF/PDB/JSON in `predictions_flat/rf3/`

Boltz smoke:

- job: `123385`
- status: FAILED, `00:02:33`, exit `1:0`
- GPU check before failure: `torch.cuda.is_available=True`, RTX3090
- failure: `urllib.error.URLError: <urlopen error [Errno 101] Network is unreachable>`
- point of failure: automatic download of `mols.tar` / Boltz model cache
- interpretation: Boltz runtime is installed, but prediction cannot run on
  compute nodes until `/public/home/yinyifan/protein_design/weights/boltz` is
  populated offline or from a network-enabled host.

## Top-3 Cross-Validation

Run directory:

```text
examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/
```

Inputs:

- `canonical/canonical_manifest.tsv`
- `prediction_inputs/rf3/*.rf3.json`
- `prediction_inputs/boltz/*.boltz.yaml`
- `reports/af3_filter_summary.csv`

Jobs:

| job | id | state | elapsed | exit |
| --- | ---: | --- | ---: | --- |
| RF3 smoke | 123384 | COMPLETED | 00:01:15 | 0:0 |
| Boltz smoke | 123385 | FAILED | 00:02:33 | 1:0 |
| RF3 top-3 | 123386 | COMPLETED | 00:01:51 | 0:0 |
| Boltz top-3 | 123387 | FAILED | 00:02:33 | 1:0 |
| final merge | 123391 | COMPLETED | 00:00:03 | 0:0 |

Summary:

- AF3 primary predictions: 3/3 successful, 3/3 PASS.
- RF3 optional predictions: 3/3 successful structure outputs, 0/3 PASS.
- Boltz optional predictions: 0/3 successful; all failed before structure
  output because compute nodes have no outbound network for cache download.
- Designs with AF3/RF3/Boltz motif RMSD all passing: 0.
- High-confidence consensus designs: none.
- AF3-only positives to downgrade: `design_1`, `design_4`, `design_9`.
- Model conflicts: `design_1`, `design_4`, `design_9`.

RF3 produced structures for all three candidates, but motif RMSD was not
interpretable with the current motif mapping: the RF3 folded sequence outputs
are numbered from the folded chain, while the motif TSV still refers to 5TPN
residues `A163-181`. The RF3 rows therefore have `motif_atoms_missing=76`.
Next RF3 adapter work should preserve or emit a residue-mapping file from
canonical design positions to original motif residues before RF3 is used for
motif-RMSD gating.

Primary result files:

- `reports/consensus_summary.csv`
- `reports/consensus_summary.json`
- `reports/run_report.json`
- `reports/rf3_filter_summary.csv`
- `reports/boltz_filter_summary.csv`
- `predictions_flat/rf3/*.pdb`
- `predictions_flat/rf3/*.cif`

## Next Steps

1. Populate Boltz cache offline:
   `/public/home/yinyifan/protein_design/weights/boltz/mols.tar`,
   extracted `mols/`, `boltz2_conf.ckpt`, and any required affinity checkpoint
   if affinity mode is used.
2. Rerun only `run_boltz_predict.sbatch` and the final merge after cache is in
   place.
3. Add an RF3 motif mapping adapter before treating RF3 motif RMSD as a hard
   design gate.
