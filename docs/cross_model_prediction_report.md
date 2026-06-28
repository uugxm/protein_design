# Cross-Model Prediction Backend Report

Date: 2026-06-28

Scope: decouple prediction inputs from model-specific formats. AF3 remains the
primary prediction backend. Foundry RF3 and Boltz are optional cross-validation
backends for AF3 top candidates only.

## Boundary

AF3 `*_data.json` is not a cross-model interchange format.

- AF3 Stage 1 writes AF3-internal `*_data.json`.
- AF3 Stage 2 may consume those files with `--run_data_pipeline=False`.
- RF3 and Boltz inputs must be generated from canonical prediction inputs plus
  optional extracted MSA/template assets.
- RF3/Boltz adapters must not directly read AF3 `*_data.json` internals.

## Canonical Prediction Input Layer

New script:

```bash
scripts/make_canonical_prediction_inputs.py
```

Inputs:

- ProteinMPNN FASTA
- optional chain metadata TSV
- reference PDB
- motif TSV
- optional generated backbone PDB

Outputs:

- `canonical/fasta/<job>.fasta`
- `canonical/json/<job>.json`
- `canonical/cif/<job>.cif`
- `canonical_manifest.tsv`
- `chain_metadata.tsv`

Canonical schema: `protein_design.canonical_prediction_input.v1`.

The canonical JSON stores stable design metadata, chain sequence records,
reference/motif provenance, and paths to canonical FASTA/CIF assets. It does not
copy AF3-specific fields such as `unpairedMsa`, `pairedMsa`, or `templates`.

## AF3 Stage 1 Asset Extraction

New script:

```bash
scripts/extract_af3_stage1_assets.py
```

It scans AF3 Stage 1 output for `*_data.json`, keeps a raw copy for AF3 Stage 2,
and writes `af3_stage1_asset_manifest.tsv` with:

- `job_name`
- `chain_id`
- `sequence`
- `unpaired_msa`
- `paired_msa`
- `template_metadata`
- `raw_af3_data_json`
- `parse_status`

If AF3 fields shift, the extractor still records a manifest row and keeps the
raw AF3 data JSON as AF3-only input.

## Model-Specific Adapters

New scripts:

```bash
scripts/make_rf3_json_inputs.py
scripts/make_boltz_inputs.py
```

RF3 adapter output:

```json
{
  "name": "<job>",
  "components": [
    {
      "seq": "<sequence>",
      "chain_id": "A",
      "msa_path": "<optional a3m>"
    }
  ]
}
```

Boltz adapter output:

```yaml
version: 1
sequences:
  - protein:
      id: "A"
      sequence: "<sequence>"
      msa: "<optional a3m>"
properties: []
```

Both adapters read canonical JSON/manifest plus optional
`af3_stage1_asset_manifest.tsv`; neither consumes AF3 internal data JSON.

## SLURM Templates

Added templates:

```text
scripts/slurm_templates/run_af3_stage1.sbatch
scripts/slurm_templates/run_af3_inference.sbatch
scripts/slurm_templates/run_rf3_predict.sbatch
scripts/slurm_templates/run_boltz_predict.sbatch
```

Partition policy:

- `run_af3_stage1.sbatch`: AMD, `--run_inference=False`
- `run_af3_inference.sbatch`: RTX3090, `--run_data_pipeline=False`
- `run_rf3_predict.sbatch`: RTX3090, `rf3 fold inputs=<native RF3 JSON dir>`
- `run_boltz_predict.sbatch`: RTX3090, `boltz predict <native Boltz input dir>`

`run_epitope_scaffold_array.sbatch` now creates canonical prediction inputs
before dispatching `PREDICTOR=af3`, `PREDICTOR=rf3`, or `PREDICTOR=boltz`.

## Collector

`scripts/collect_prediction_outputs.py` now supports:

```text
--predictor af3
--predictor rf3
--predictor boltz
```

It writes a flat manifest plus JSON/PDB/CIF outputs where available. CIF and
CIF.GZ structures are converted to PDB for `filter_designs.py`, while the flat
CIF is preserved for traceability.

Consensus merger:

```bash
scripts/compare_prediction_backends.py
```

It merges AF3/RF3/Boltz filter summaries into `consensus_summary.csv`, preserving
predictor-specific confidence, motif RMSD, clash counts, output paths, and
failure reasons.

## Top-3 Cross-Validation Test

Run directory:

```text
examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/
```

Input candidates: top 3 AF3-ranked RFdiffusion v1 designs from:

```text
examples/epitope_scaffold/backend_comparison_5tpn_foundry_20260628_213554/rfdiffusion_v1/reports/top_designs.csv
```

Candidates:

| design_id | AF3 pass | AF3 pLDDT | AF3 PAE | AF3 motif RMSD | AF3 clashes |
| --- | --- | ---: | ---: | ---: | ---: |
| design_9 | PASS | 91.4301 | 2.6374 | 1.04193 | 0 |
| design_1 | PASS | 90.4390 | 2.72235 | 0.721181 | 0 |
| design_4 | PASS | 87.2266 | 3.35261 | 1.84953 | 0 |

Generated assets:

```text
canonical/canonical_manifest.tsv
canonical/chain_metadata.tsv
prediction_inputs/rf3/*.rf3.json
prediction_inputs/boltz/*.boltz.yaml
reports/af3_filter_summary.csv
reports/rf3_filter_summary.csv
reports/boltz_filter_summary.csv
reports/consensus_summary.csv
reports/run_report.json
logs/*.out
logs/*.err
job_ids.env
```

SLURM jobs:

| backend | job id | result | reason |
| --- | ---: | --- | --- |
| RF3 first attempt | 123381 | FAILED | invalid Hydra override copied from RFD3-style config |
| RF3 retry | 123383 | FAILED | missing checkpoint `weights/foundry/rf3_foundry_01_24_latest_remapped.ckpt` |
| Boltz | 123382 | FAILED | `boltz: command not found` |

Important: RF3 and Boltz input generation succeeded. Prediction did not produce
structures because the optional backend runtimes are incomplete.

Summary file:

```text
examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628/reports/consensus_summary.csv
```

Current interpretation:

- AF3 primary predictions are available and pass filters for all top 3 designs.
- RF3 native JSON inputs are ready, but RF3 requires the missing Foundry RF3
  checkpoint before prediction can run.
- Boltz native YAML inputs are ready, but a Boltz runtime environment still
  needs to be installed before prediction can run.

## Next Steps

1. Install/configure Foundry RF3 checkpoint:

```bash
cd ~/protein_design
foundry install rf3 --checkpoint-dir ~/protein_design/weights/foundry
```

or place/symlink:

```text
~/protein_design/weights/foundry/rf3_foundry_01_24_latest_remapped.ckpt
```

2. Install Boltz in an isolated environment:

```bash
cd ~/protein_design
# create envs/boltz without modifying base conda
```

3. Rerun only optional cross-validation:

```bash
cd ~/protein_design
RUN=examples/epitope_scaffold/cross_model_prediction_top3_5tpn_20260628
sbatch --chdir "$RUN" \
  --export=ALL,PROTEIN_DESIGN_HOME=$PWD,CANONICAL_MANIFEST=$PWD/$RUN/canonical/canonical_manifest.tsv,DESIGN_ID=cross_model_top3 \
  scripts/slurm_templates/run_rf3_predict.sbatch

sbatch --chdir "$RUN" \
  --export=ALL,PROTEIN_DESIGN_HOME=$PWD,CANONICAL_MANIFEST=$PWD/$RUN/canonical/canonical_manifest.tsv,DESIGN_ID=cross_model_top3 \
  scripts/slurm_templates/run_boltz_predict.sbatch
```

Then run `filter_designs.py` on each predictor's flat outputs and regenerate
`reports/consensus_summary.csv` with `compare_prediction_backends.py`.
