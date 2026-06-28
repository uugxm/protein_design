# Cross-Model Prediction Backend Report

Date: 2026-06-29

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
- cache status: populated offline, then unpacked on AMD job `123393`.

Boltz cache files:

| file | size bytes | sha256 |
| --- | ---: | --- |
| `mols.tar` | `1855662080` | `39e076d96dbec6b4e86982bbda16f3a53a2a60c9bdc17828d88f6f9a0c7d1fd7` |
| `boltz2_conf.ckpt` | `2286561469` | `090e82ac8c92f5e943fa1b39e7410a44027bea7243c0bbb3caa67a77fc1428e1` |
| `boltz2_aff.ckpt` | `2062139170` | `dcc5cd3722b1c9eaa34267e4ae32f55cbbf1963f4c19319381ccfa30fdd2ca9e` |

The cache directory is about 7.5G after extracting `mols/`. The large cache
files are not tracked in git; only `docs/install_logs/boltz_cache_sha256_20260629.txt`
and `docs/install_logs/boltz_cache_files_20260629.txt` are tracked.

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

`scripts/slurm_templates/run_boltz_predict.sbatch` now:

- fails fast if `mols.tar`, extracted `mols/`, `boltz2_conf.ckpt`, or
  `boltz2_aff.ckpt` are missing;
- writes `boltz_manifest.tsv` outside `prediction_inputs/boltz/`, because
  Boltz parses every file in the input directory;
- supports batch directory input and clears stale flat outputs before collection.

`scripts/collect_prediction_outputs.py` now treats Boltz batch outputs as
multiple per-design prediction roots under `predictions/*/*.boltz/`.

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

- previous failed job: `123385`, failed while compute-node network tried to
  download cache files.
- cache prep job: `123393`, COMPLETED, exit `0:0`; unpacked `mols/` and
  verified checkpoint SHA256.
- successful smoke job: `123394`, COMPLETED, `00:00:48`, exit `0:0`
- GPU check: `torch.cuda.is_available=True`, RTX3090
- output: `examples/epitope_scaffold/boltz_smoke_single_chain_20260628/predictions_flat/boltz/boltz_smoke_single_chain.pdb`
- collector: generated flat CIF/PDB/JSON and manifest.

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

Relevant jobs:

| job | id | state | elapsed | exit |
| --- | ---: | --- | ---: | --- |
| RF3 smoke | 123384 | COMPLETED | 00:01:15 | 0:0 |
| RF3 top-3 | 123386 | COMPLETED | 00:01:51 | 0:0 |
| RF3 mapping/finalize fix | 123392 | COMPLETED | 00:00:03 | 0:0 |
| Boltz cache prep | 123393 | COMPLETED | 00:00:50 | 0:0 |
| Boltz smoke after cache | 123394 | COMPLETED | 00:00:48 | 0:0 |
| Boltz top-3 after cache | 123397 | COMPLETED | 00:00:43 | 0:0 |
| Boltz batch recollect | 123399 | COMPLETED | 00:00:01 | 0:0 |
| final merge with RF3/Boltz mappings | 123401 | COMPLETED | 00:00:03 | 0:0 |

Summary from `reports/consensus_summary.csv`:

- AF3 primary predictions: 3/3 successful, 3/3 PASS.
- RF3 optional predictions: 3/3 successful, 3/3 PASS.
- Boltz optional predictions: 3/3 successful, 0/3 PASS.
- Designs with AF3/RF3/Boltz motif RMSD all passing: 0.
- AF3/RF3 recommended designs: `design_1`, `design_9`, `design_4`.
- AF3-only positives to downgrade: none.
- Model conflicts: `design_1`, `design_4`, `design_9`.

Top design recommendation uses AF3+RF3 consensus as the main decision layer.
Boltz single-sequence disagreement is recorded as a warning, not as a hard
filter:

| rank | design | AF3 motif RMSD | RF3 motif RMSD | mean AF3/RF3 pLDDT | mean AF3/RF3 PAE | Boltz warning |
| ---: | --- | ---: | ---: | ---: | ---: | --- |
| 1 | `design_1` | 0.721181 | 0.750603 | 88.3829 | 2.22146 | low pLDDT; high motif RMSD |
| 2 | `design_9` | 1.04193 | 1.04981 | 90.5222 | 2.00686 | low pLDDT; high motif RMSD |
| 3 | `design_4` | 1.84953 | 1.67975 | 80.5991 | 5.37947 | low pLDDT; high motif RMSD; one missing motif atom |

The machine-readable recommendation table is
`reports/top_consensus_designs.csv`.

RF3 motif mapping is now generated from the conserved motif sequence
`EVNKIKSALLSTNKAVVSL` in the folded output PDBs. RF3 motif RMSD values are:

| design | RF3 pLDDT | RF3 PAE | RF3 motif RMSD | RF3 pass |
| --- | ---: | ---: | ---: | --- |
| `design_1` | 86.3269 | 1.72056 | 0.750603 | PASS |
| `design_4` | 73.9715 | 7.40633 | 1.67975 | PASS |
| `design_9` | 89.6143 | 1.37633 | 1.04981 | PASS |

Boltz produced valid structures for all three candidates, but single-sequence
Boltz did not preserve the 5TPN motif geometry. Boltz motif RMSD values are
about 546-552 A and confidence is below the pLDDT threshold:

| design | Boltz pLDDT | Boltz pTM | Boltz motif RMSD | Boltz pass |
| --- | ---: | ---: | ---: | --- |
| `design_1` | 65.4649 | 0.2995 | 552.226 | FAIL |
| `design_4` | 59.2929 | 0.28141 | 546.501 | FAIL |
| `design_9` | 69.1138 | 0.297341 | 549.851 | FAIL |

Interpretation: AF3 and RF3 agree that the top candidates preserve the motif
under the current thresholds. Boltz, run in no-MSA single-sequence mode, strongly
disagrees and should be treated as an optional conflict flag rather than a hard
primary filter.

Boltz disagreement diagnostics were run for `design_1` and `design_9`.

- Both sampled Boltz outputs have complete motif sequence-derived mappings:
  76 backbone motif atoms compared, 0 missing.
- The collector selected the expected Boltz CIFs recorded in
  `predictions_flat/boltz/cross_model_top3.prediction_manifest.json`.
- The original Boltz CIF coordinates already have hundreds-of-Angstrom
  coordinate ranges, so the disagreement is not introduced by CIF-to-PDB
  conversion.
- Consecutive CA distances are hundreds of Angstroms in the full chain and
  inside the mapped motif.

Conclusion: Boltz no-MSA mode is not reliable as a hard gate for this de novo
motif scaffold task. It should remain an optional conflict flag until
MSA/template-enabled validation is tested.

Primary result files:

- `reports/consensus_summary.csv`
- `reports/consensus_summary.json`
- `reports/run_report.json`
- `reports/top_consensus_designs.csv`
- `reports/boltz_disagreement_diagnostics.md`
- `reports/rf3_filter_summary.csv`
- `reports/boltz_filter_summary.csv`
- `reports/boltz_motif_diagnostics/*.tsv`
- `reports/boltz_motif_diagnostics/*_aligned.pdb`
- `reports/boltz_motif_diagnostics/*.pml`
- `predictions_flat/rf3/*.pdb`
- `predictions_flat/boltz/*.pdb`
- `predictions_flat/rf3_mappings/*.trb`
- `predictions_flat/boltz_mappings/*.trb`

## Next Steps

1. Keep AF3 as the primary prediction backend and RF3/Boltz as optional
   cross-validation on AF3 top candidates.
2. Treat Boltz single-sequence conflicts as deprioritization evidence, not as
   replacement for AF3 filtering.
3. If Boltz is used more broadly, add MSA/template assets through the canonical
   asset manifest before interpreting motif RMSD as a hard gate.
