---
name: epitope_scaffold_design
description: Use for auditable epitope or motif scaffold design from antigen complexes, RFdiffusion v1 or Foundry RFD3 backbone generation, fixed-motif ProteinMPNN design, AF3/RF3/Boltz prediction checks, filtering, clustering, pre-order QC, and final candidate packaging.
---

# Epitope Scaffold Design

## Purpose

Use this skill for epitope scaffold and motif scaffold design when a known antigen motif must be displayed on a new scaffold. It covers:

- extracting an epitope or motif from an antigen-antibody or antigen-ligand complex
- preparing motif inputs for RFdiffusion v1 and Foundry RFD3
- generating scaffold backbones with RFdiffusion v1 or Foundry RFD3
- designing fixed-motif sequences with ProteinMPNN or LigandMPNN where available
- running AF3 as the primary prediction check, RF3 as optional confirmation, and Boltz as an optional warning layer
- computing motif RMSD, clash count, fold clustering, pre-order QC, and final candidate packaging

## When to use

Use this skill when:

- a linear or local conformational epitope must be reconstructed
- a known epitope or motif must be grafted onto a de novo scaffold
- RFdiffusion v1 and Foundry RFD3 motif scaffolding performance must be compared on the same input
- experimental candidates, expression pre-QC, or a cloning-ready placeholder table are needed

Use caution or route elsewhere when:

- the epitope is completely unknown
- the epitope has multiple distant discontinuous segments without reasonable spatial constraints
- the request is direct antibody paratope design; route to RFantibody or an antibody-design skill
- ligand, metal, or cofactor geometry is a hard constraint but no all-atom input definition exists

## Input contract

Minimal inputs:

- reference PDB or mmCIF
- motif residue specification TSV with `chain` and either `residue` or `start/end`
- chain ID
- output root
- backbone backend: `rfdiffusion_v1` or `foundry_rfd3`

Complex-derived inputs:

- antigen-antibody complex PDB or mmCIF
- antigen chain ID
- antibody heavy chain ID
- antibody light chain ID
- heavy atom contact distance cutoff, default 4.0-5.0 Angstrom
- optional epitope residue whitelist or blacklist
- optional original-paper motif residues for reproduction comparison

Backend config:

- RFdiffusion v1 contig template
- Foundry RFD3 input JSON template
- length bins
- number of backbones
- number of ProteinMPNN sequences per backbone
- AF3 and RF3 prediction limits

RFD3 usage policy:

- Do not treat Foundry RFD3 as a simple RFdiffusion v1 contig replacement; use the atom-level Foundry input model intentionally.
- For epitope scaffold work, default RFD3 fixed motif conditioning to `ALL` motif heavy atoms unless running an explicit `BKBN` ablation.
- For the RSV F site V benchmark, the calibrated continuous RFD3 setting is `A163-181 + all_motif_heavy_atoms + 20-30/motif/20-30`.
- Do not start RFD3 Phase 2 production for site V until contact-core and discontinuous/contact-derived pilots are reviewed.
- See `docs/rfd3_paper_usage_review.md` for the full strategy and required RFD3 parameter/QC record.

## Workflow

Current smoke benchmark orchestration is semi-automated: backbone generation, MPNN, AF3, and summary are submitted through workflow wrappers; RF3 confirmation, clustering, pre-order QC, and final packaging may still be run as downstream staged steps unless the full DAG wrapper is explicitly invoked.

Step 0. Validate input complex and chains.

Step 1. Extract or confirm motif residues with `scripts/prepare_epitope_from_complex.py`; record contact cutoff, chain mapping, mutations, missing residues, and motif provenance.

Step 2. Generate backend-specific motif input:

- RFdiffusion v1 contig, for example `[10-40/A163-181/10-40]`
- Foundry RFD3 JSON from `scripts/make_rfd3_motif_input.py`

Step 3. Generate backbones:

- RFdiffusion v1 through `scripts/slurm_templates/run_backbone_generation.sbatch`
- Foundry RFD3 through the same launcher with `BACKBONE_BACKEND=foundry_rfd3`

Step 4. Normalize outputs into a common `backbone_list.txt` format with design PDBs and TRB/mapping sidecars.

Step 5. Run ProteinMPNN fixed-position sequence design using motif mapping from TRB when present.

Step 6. Run AF3 primary prediction and filtering.

Step 7. Run RF3 confirmation on top AF3 candidates.

Step 8. Run Boltz only as a warning layer unless MSA/template-enabled validation is available.

Step 9. Filter on motif atoms present, motif RMSD, pLDDT, PAE, and clash count.

Step 10. Cluster global fold, motif-local geometry, and sequence diversity.

Step 11. Run pre-order QC with no expression-system assumptions.

Step 12. Package final candidates with sequences, structures, QC JSON, motif mapping, and PyMOL views.

## Required scripts

`scripts/prepare_epitope_from_complex.py`

- input: complex PDB or mmCIF, antigen chain, antibody chains
- output: `motif_residues.tsv`, `epitope_contact_map.tsv`, `antigen_antibody_interface_summary.csv`, `motif_reference.pdb`, `motif_extraction_report.md`
- computes heavy atom contacts, heavy/light contribution, continuous versus discontinuous segmentation, contact residue count, and fragmentation warnings

`scripts/run_epitope_scaffold_workflow.py`

- orchestrates backbone generation, ProteinMPNN, prediction, filtering, summary comparison, and handoff points for RF3/clustering/QC
- calls existing scripts and Slurm templates rather than duplicating the validated workflow

`scripts/benchmark_backbone_backends.py`

- compares RFdiffusion v1 and Foundry RFD3 on the same motif input
- produces `backend_comparison_summary.csv`

`scripts/package_final_candidates.py`

- creates `final_candidates/`
- copies FASTA, PDB, CIF, TRB, QC, and PyMOL files
- writes `package_manifest.tsv`

## Output contract

Every run must contain:

```text
run_params.json
job_ids.env
logs/
reports/
  motif_extraction_report.md
  backend_generation_summary.csv
  all_filter_summary.csv
  consensus_summary.csv
  fold_cluster_summary.csv
  diverse_shortlist.csv
  pre_order_sequence_qc.csv
  pre_order_structure_qc.csv
  pre_order_qc_decision.csv
  final_candidate_selection_report.md
final_candidates/
  design_X/
    sequence.fasta
    af3_model.pdb
    rf3_model.pdb
    backbone.pdb
    motif_mapping.tsv
    motif_aligned.pdb
    qc.json
    summary.md
    motif_qc.pml
```

## Decision policy

Primary quality gate:

- AF3 PASS
- `motif_atoms_missing = 0`
- motif RMSD below the run threshold
- pLDDT and PAE thresholds pass
- clash count acceptable

Confirmation gate:

- RF3 PASS is required for final primary candidates.

Diversity gate:

- global fold cluster
- motif-local cluster
- sequence cluster

Warning layer:

- Boltz no-MSA conflict warning
- low motif exposure proxy
- NXS/T motif if eukaryotic secretory expression is planned
- low-complexity region or hydrophobic stretch

Ordering gate:

- `cloning_ready_constructs.csv` may be generated only after pre-order QC
- no tag, signal peptide, linker, restriction site, or codon optimization may be added unless the expression system and vector are specified

## Safety / correctness constraints

- Never treat AF3 `*_data.json` as RF3 or Boltz input.
- Never hard-code epitope residues without recording provenance.
- Never call a Boltz no-MSA failure a hard rejection unless it is validated with MSA/template-enabled Boltz.
- Never mark a construct as final order-ready until expression system, vector, tags, signal peptide, and codon optimization policy are specified.
- Always record exact backend version, checkpoint path, command, runtime, job IDs, and thresholds.
- Never run compute on a login node; use Slurm for backbone generation and structure prediction.

## Example

RSV F site V / hRSV90 epitope scaffold reproduction from PDB 5TPN.

```bash
bash examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/run_smoke_benchmark.sh
```

Expected outputs:

- `reports/motif_extraction_report.md`
- `reports/backend_comparison_summary.csv`
- `reports/diverse_shortlist.csv`
- `reports/pre_order_qc_decision.csv`
- `reports/final_candidate_selection_report.md`
