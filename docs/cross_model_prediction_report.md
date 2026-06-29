# Cross-Model Prediction Policy

AF3 is the primary prediction backend for this stack. Foundry RF3 and Boltz are
optional cross-validation backends that should normally be run only on AF3 top
candidates.

## Input Boundary

AF3 `*_data.json` files are AF3-internal Stage 1 assets for AF3 Stage 2
inference. They are not a canonical cross-model format.

RF3 and Boltz inputs must be generated from:

- canonical sequence/structure input manifests,
- chain metadata,
- reference motif metadata,
- optional extracted MSA/template asset manifests.

Use:

- `scripts/make_canonical_prediction_inputs.py`
- `scripts/extract_af3_stage1_assets.py`
- `scripts/make_rf3_json_inputs.py`
- `scripts/make_boltz_inputs.py`
- `scripts/collect_prediction_outputs.py`

## Historical Conclusion

The pilot cross-model tests established the current policy:

- AF3 remains the primary validation backend.
- RF3 is useful as independent confirmation for promoted designs.
- Boltz can run as a warning/conflict flag, but no-MSA single-sequence Boltz
  disagreement is not reliable as a hard rejection gate for de novo motif
  scaffolds.

Runtime prediction trees, model files, logs, and candidate packages from those
pilot tests are no longer tracked in git.
