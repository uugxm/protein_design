#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE="${PROTEIN_DESIGN_HOME:-$(cd "$ROOT/../.." && pwd)}"
export PROTEIN_DESIGN_HOME="$BASE"

INPUT_PDB="${INPUT_PDB:-$ROOT/inputs/5TPN.pdb}"
ANTIGEN_CHAIN="${ANTIGEN_CHAIN:-A}"
HEAVY_CHAIN="${HEAVY_CHAIN:-H}"
LIGHT_CHAIN="${LIGHT_CHAIN:-L}"
MOTIF_TSV="${MOTIF_TSV:-$ROOT/inputs/motif_residues_benchmark.tsv}"
V1_CONTIGS="${V1_CONTIGS:-[10-40/A163-181/10-40]}"
SUBMIT="${SUBMIT:-1}"

if [ ! -s "$INPUT_PDB" ]; then
  echo "Missing input PDB: $INPUT_PDB" >&2
  exit 2
fi

mkdir -p "$ROOT/inputs" "$ROOT/reports" "$ROOT/logs"

python3 "$BASE/scripts/prepare_epitope_from_complex.py" \
  --complex "$INPUT_PDB" \
  --antigen_chain "$ANTIGEN_CHAIN" \
  --antibody_heavy_chain "$HEAVY_CHAIN" \
  --antibody_light_chain "$LIGHT_CHAIN" \
  --cutoff 4.0 \
  --out_dir "$ROOT/inputs" \
  --motif_tsv "$ROOT/inputs/motif_residues_contact4.tsv" \
  --contact_map_tsv "$ROOT/inputs/epitope_contact_map_contact4.tsv" \
  --summary_csv "$ROOT/reports/antigen_antibody_interface_summary_contact4.csv" \
  --motif_reference_pdb "$ROOT/inputs/motif_reference_contact4.pdb" \
  --report_md "$ROOT/reports/motif_extraction_report_contact4.md" \
  --cleaned_pdb "$ROOT/inputs/5TPN_cleaned.pdb" \
  --chain_mapping_tsv "$ROOT/inputs/chain_mapping.tsv" \
  --antigen_pdb "$ROOT/inputs/antigen_chain_A.pdb" \
  --antibody_pdb "$ROOT/inputs/hRSV90_heavy_light.pdb"

python3 "$BASE/scripts/prepare_epitope_from_complex.py" \
  --complex "$INPUT_PDB" \
  --antigen_chain "$ANTIGEN_CHAIN" \
  --antibody_heavy_chain "$HEAVY_CHAIN" \
  --antibody_light_chain "$LIGHT_CHAIN" \
  --cutoff 5.0 \
  --out_dir "$ROOT/inputs" \
  --motif_tsv "$ROOT/inputs/motif_residues_contact5.tsv" \
  --contact_map_tsv "$ROOT/inputs/epitope_contact_map.tsv" \
  --summary_csv "$ROOT/reports/antigen_antibody_interface_summary_contact5.csv" \
  --motif_reference_pdb "$ROOT/inputs/motif_reference_contact5.pdb" \
  --report_md "$ROOT/reports/motif_extraction_report.md"

submit_args=(--dry_run)
if [ "$SUBMIT" = "1" ]; then
  submit_args=(--submit)
fi

python3 "$BASE/scripts/run_epitope_scaffold_workflow.py" \
  --phase smoke \
  --benchmark_root "$ROOT" \
  --input_pdb "$INPUT_PDB" \
  --reference_pdb "$INPUT_PDB" \
  --motif_tsv "$MOTIF_TSV" \
  --backends "rfdiffusion_v1,foundry_rfd3" \
  --num_backbones "${NUM_BACKBONES:-20}" \
  --num_seq "${NUM_PROTEINMPNN_SEQUENCES:-4}" \
  --af3_per_backbone "${AF3_PER_BACKBONE:-1}" \
  --rf3_top_n "${RF3_TOP_N:-5}" \
  --v1_contigs "$V1_CONTIGS" \
  --foundry_nterm_range "${FOUNDRY_RFD3_NTERM_RANGE:-10-40}" \
  --foundry_cterm_range "${FOUNDRY_RFD3_CTERM_RANGE:-10-40}" \
  --foundry_batch_size "${FOUNDRY_RFD3_BATCH_SIZE:-2}" \
  --min_plddt "${MIN_PLDDT:-70}" \
  --max_pae "${MAX_PAE:-10}" \
  --max_motif_rmsd "${MAX_MOTIF_RMSD:-2.5}" \
  --max_clashes "${MAX_CLASHES:-20}" \
  "${submit_args[@]}"
