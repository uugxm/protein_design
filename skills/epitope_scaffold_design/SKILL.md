# Epitope Scaffold Design Workflow Skill

## Purpose

Use this skill to design de novo scaffold proteins that preserve a specified epitope or structural motif, redesign the surrounding scaffold sequence, and triage candidates with independent structure prediction and motif-specific QC.

The reusable workflow is:

1. Define the motif from a provenance-backed structure and residue selection.
2. Generate scaffold backbones with the backend that matches the motif geometry.
3. Redesign scaffold sequence while preserving the motif.
4. Predict structures with AF3 as the primary validator.
5. Confirm high-priority designs with RF3 when available.
6. Apply motif, confidence, clash, diversity, and downstream experimental-readiness gates.

Historical benchmark runs can inform thresholds and failure modes, but they are not required inputs and must not be treated as live entrypoints.

## When to use

Use this workflow when the user wants to:

- Graft a continuous epitope, loop, helix, strand, or other protein motif into a new scaffold.
- Preserve residue identity and geometry for a structurally defined antigenic, binding, or functional motif.
- Compare RFdiffusion v1 and Foundry RFD3 for a motif-scaffolding problem.
- Produce AF3/RF3/Boltz prediction inputs and motif-specific QC summaries for candidate selection.
- Prepare a shortlist for expression, phage display, synthesis, or downstream experimental review.

## When not to use

Do not use this workflow when:

- The motif has no reliable structural provenance or residue definition.
- The user only needs generic protein folding or sequence optimization without a fixed structural motif.
- The task is antibody, binder, enzyme, or ligand-pocket design where a dedicated workflow is available and motif scaffolding is only incidental.
- The requested output is cloning-ready material but expression host, vector, tag, secretion/localization, linker, cleavage, and codon policy are not defined.
- The user expects a single predictor score, raw motif RMSD, or a benchmark rank to substitute for experimental validation.

## Backend policy

Default backend selection:

- Use `rfdiffusion_v1` as the primary production backbone generator for simple continuous protein motifs.
- Use `foundry_rfd3` for all-atom, contact-aware, discontinuous, sidechain-sensitive, ligand, nucleic-acid, cofactor, or non-protein contexts.
- Use `foundry_rf3` only as a folding or prediction backend, not as a backbone generator.

Sequence design:

- Use ProteinMPNN by default for protein-only scaffold sequence design with fixed motif positions.
- Use LigandMPNN when the design depends on ligand, non-protein, atom-level contact, metal, cofactor, or contact-aware constraints.

Prediction and validation:

- Use AF3 as the primary structure-prediction validator.
- Use RF3 as independent confirmation for promoted or borderline candidates.
- Use Boltz only as an optional conflict or warning signal unless MSA/template-enabled Boltz validation has been tested for the exact use case. No-MSA Boltz can strongly disagree on de novo motif scaffolds and must not be a hard fail by default.

## Motif definition policy

Every run must record motif provenance before backbone generation:

- Reference structure identifier or source file, including version/date when known.
- Chain IDs, residue numbers, insertion codes if present, and residue names.
- Whether residue numbering is author, label, renumbered, or model-derived.
- Motif TSV or equivalent machine-readable interval/selection file.
- Whether fixed atoms are backbone-only or all heavy atoms.
- Biological rationale for the selected motif and any excluded contacting residues.

Continuous motifs:

- RFdiffusion v1 may use slash-style contigs such as `[N-M/A10-25/N-M]`.
- Foundry RFD3 uses comma-separated contigs such as `N-M,A10-25,N-M`; use `/0` only for chain breaks.

Discontinuous motifs:

- Do not force discontinuous motifs into a fake continuous contig.
- Prefer Foundry RFD3 or another contact-aware/all-atom route that can represent separated selections directly.
- If the current wrappers require interval TSV rows, preserve each interval as its own row and document any unsupported constraint before running.

Fixed atoms:

- Use `BKBN` when only backbone geometry must be fixed and sidechains can be redesigned or relaxed.
- Use `ALL` when sidechain atom placement is part of the epitope or contact surface and must be preserved.
- Do not mix `ALL` and `BKBN` silently; record the selected mode in `run_params.json` or the run report.

## RFD3 policy

Use Foundry RFD3 when the motif problem benefits from next-generation all-atom/contact-aware modeling:

- Discontinuous protein motifs.
- Sidechain-critical epitopes or paratopes.
- Ligands, cofactors, metals, nucleic acids, glycans, or other non-protein partners.
- Explicit contact preservation around an epitope.
- Cases where RFdiffusion v1 contigs cannot represent the design intent cleanly.

RFD3 input policy:

- Use InputSpecification JSON/YAML or the repository adapter that writes that format.
- Record `input`, `contig`, `select_fixed_atoms`, `select_unfixed_sequence` when used, `length`, `is_non_loopy`, `partial_t`, and sampler parameters.
- Record sampler settings such as `inference_sampler.num_timesteps`, `diffusion_batch_size`, `n_batches`, random seed, checkpoint, and Foundry/rc-foundry version.
- Normalize Foundry outputs into the downstream backbone plus mapping contract before ProteinMPNN/LigandMPNN and QC.

Do not use AF3 `*_data.json` assets as RF3 or Boltz inputs. RF3 and Boltz inputs must be generated from canonical sequence/structure manifests or their own native input adapters.

## QC policy

Promote candidates only after combined evidence review:

- Motif preservation in predicted structures, not just raw generated-backbone motif RMSD.
- AF3 confidence, PAE, clashes, missing residues, chain breaks, and local support around the motif.
- RF3 agreement for priority candidates when available.
- Sequence plausibility: length, cysteine pattern, glycosylation liabilities when relevant, aggregation-prone regions, repeats, low complexity, charge, and hydrophobic exposure.
- Fold and sequence diversity so the shortlist does not collapse to one topology.
- Experimental readiness gates for the intended assay or expression system.

Required motif QC:

- Align predicted model motif atoms to the reference motif using the recorded mapping.
- Report motif RMSD and atom coverage for backbone atoms at minimum; include sidechain/all-heavy-atom RMSD when `ALL` atoms were fixed.
- Inspect local support residues around the motif, especially residues within 6-10 Angstrom.
- Flag designs where the motif passes RMSD but the display geometry, access, clashes, or confidence is poor.

Do not promote based only on raw RFdiffusion/RFD3 motif RMSD. Raw motif RMSD is a generation diagnostic, not a final selection rule.

Phage display or wet-screening readiness:

- Include exposed motif access, scaffold stability/confidence, termini placement, cysteine/disulfide risk, stop/frameshift-free sequence, library diversity intent, and display-fusion compatibility.
- Do not call candidates cloning-ready unless expression host, vector, tag/fusion, linker, secretion/localization, codon optimization, restriction/Gibson/Golden Gate strategy, and sequence naming are specified.

## Output contract

Each run should produce or update:

- `run_params.json` or equivalent with input provenance, backend, motif definition, fixed atom mode, sampler parameters, sequence-design parameters, predictor settings, and thresholds.
- Backbone files and mapping files for each design, including generated `.pdb`/`.cif` and motif residue mapping.
- ProteinMPNN or LigandMPNN outputs, including all sampled sequences and fixed-position/contact constraints.
- Predictor-neutral canonical inputs before AF3/RF3/Boltz conversion.
- AF3 prediction inputs and outputs for primary validation.
- RF3 prediction inputs and outputs for independent confirmation when used.
- Boltz prediction inputs and outputs only when explicitly run, with a warning if no MSA/template evidence was used.
- Per-design QC JSON/CSV containing motif RMSD, atom coverage, confidence, PAE, clash count, missing atoms/residues, sequence metrics, predictor source, and pass/fail flags.
- A merged shortlist table ranking designs by combined criteria, not by one metric alone.
- A human-readable summary that separates computationally validated, experimentally promising, and cloning-ready states.

Minimum candidate state labels:

- `generated`: backbone exists but sequence/prediction QC is incomplete.
- `predicted`: AF3 or another predictor completed.
- `validated_computational`: passes motif, confidence, clash, and cross-model gates.
- `experimental_candidate`: suitable for wet review but not necessarily cloning-ready.
- `cloning_ready`: only after vector/expression/tag/linker/codon policy is complete.

## Safety/correctness constraints

- Preserve concurrent edits outside the requested ownership area. Do not revert unrelated changes.
- Do not depend on tracked runtime artifacts, benchmark output folders, or raw cluster paths for the reusable workflow.
- Do not run compute-heavy jobs on login or management nodes; submit through the appropriate scheduler/queue.
- Do not hard-code historical benchmark structures as required inputs.
- Do not silently convert discontinuous motifs into continuous contigs.
- Do not confuse RFdiffusion v1, Foundry RFD3, and Foundry RF3.
- Do not reuse AF3 stage/output `*_data.json` as RF3 or Boltz input.
- Do not hide failed predictors. Record missing, failed, skipped, and warning states explicitly.
- Do not rank by raw motif RMSD alone. Require predicted-structure motif QC plus confidence and clash checks.
- Do not label candidates as cloning-ready without expression/vector/tag/linker/codon decisions.
- Keep proprietary, unpublished, or sensitive structural inputs out of public examples unless the user explicitly approves release.
