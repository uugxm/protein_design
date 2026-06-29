# RFD3 Paper Usage Review

Date: 2026-06-29

## Purpose

This note updates the local RFD3 usage strategy after reviewing the RFD3 paper framing, the Foundry model role documentation, and the Foundry RFD3 input specification. The operational conclusion is that Foundry RFD3 should not be treated as a simple RFdiffusion v1 contig replacement. It is an atom-level diffusion backend whose strengths need different inputs, different logging, and different QC.

## Source Basis

- RFdiffusion3 paper: "De novo design of all-atom biomolecular interactions with RFdiffusion3", bioRxiv DOI `10.1101/2025.09.18.676967`.
- Foundry repository and model roles: <https://github.com/RosettaCommons/foundry>
- Foundry RFD3 input specification: <https://github.com/RosettaCommons/foundry/blob/production/models/rfd3/docs/input.md>
- Local integration record: `docs/foundry_rfd3_backend_report.md`
- Local calibration record: `docs/rfd3_parameter_sweep_report.md`

## Strategy Update

RFD3 is an atom-level diffusion model. Its expected advantage is not just "RFdiffusion v1 with a different command." It should be used when atom-level constraints, sidechain/contact-aware design, non-protein context, or discontinuous and multi-island motifs matter. The Foundry input layer supports atom-level selection, fixed atoms, residue-level and atom-level metadata, hotspot/contact-style constraints, and sampler/runtime controls that do not map cleanly onto an RFdiffusion v1 contig-only mental model.

The RSV F site V A163-181 continuous motif reproduction is a RFdiffusion v1-favorable task. It is useful as a baseline and sanity check, but it should not be the only evaluation of RFD3. A continuous peptide segment with simple flanking scaffold length bins underuses RFD3's atom-level and discontinuous-motif capability.

For epitope scaffold work, the default RFD3 motif conditioning should use `ALL` motif heavy atoms unless there is a specific reason to run a backbone-only ablation. The `BKBN` setting is useful for calibration, failure analysis, and isolating backbone geometry effects, but it is not the preferred default for contact-face epitope reproduction.

## Current Site V Recommendation

For the current RSV F site V / hRSV90 benchmark, the calibrated continuous RFD3 setting is:

```text
motif_definition: A163-181
fixed_atom_level: all_motif_heavy_atoms
length_bin: 20-30/motif/20-30
```

This setting produced the best mini-sweep result among the first three RFD3 conditions. It improved over the initial RFD3 condition, but it did not justify moving directly into a 100-200 backbone RFD3 production benchmark.

## Contact-Motif Pilot Result

The contact-motif pilot is recorded in `docs/rfd3_contact_motif_pilot_report.md`.

Pilot conclusions:

- A169-178 contact core with all motif heavy atoms and 20-30/motif/20-30 was cleanly validated and run for 20 backbones.
- The c04 raw motif RMSD median was low, supporting effective RFD3 raw motif conditioning.
- c04 did not produce contact-face pass candidates: AF3 pass rate was 9/20, RF3 confirmed 5/5 selected candidates, and contact-face QC was 0 pass / 25 caution / 0 hold.
- The contact4 discontinuous site V condition was held before GPU submission because the current local wrapper cannot cleanly audit discontinuous unindex normalization, TRB mapping, and fixed-position propagation.

These results better match RFD3's expected development path than the A163-181 continuous reproduction alone, but they still do not justify RFD3 Phase 2 production for this benchmark.

## Required RFD3 Parameter Record

Every RFD3 run must record the exact input JSON/YAML and the resolved command-line overrides. At minimum, capture:

- `select_fixed_atoms` and the atom-selection level, especially `ALL` versus `BKBN`.
- `step_scale`; also record `eta` if the installed config or output metadata exposes it.
- `gamma_0`.
- `num_timesteps`.
- `cfg_scale`.
- `center_option`.
- `allow_realignment`.
- `is_non_loopy`.
- `partial_t`.
- length bin and motif definition provenance.
- checkpoint path, Foundry package version, source commit when available, Slurm job ID, walltime, GPU model, and GPU minutes.

If a parameter is not supported by the active Foundry version, record it as `not_supported_or_not_exposed` rather than leaving it blank.

## Contact-Face And Exposure QC

RFD3 epitope-scaffold evaluation must add contact-face metrics instead of relying only on global motif RMSD:

- antibody-facing motif atom exposure.
- motif local support occlusion.
- contact residue preservation after ProteinMPNN.
- AF3 contact-face RMSD.
- RF3 contact-face RMSD.
- clash count restricted to the motif/contact face and its local scaffold shell.
- comparison of designed contact-face atom positions against the hRSV90-facing reference atoms.

The contact-face metrics should be reported next to whole-motif RMSD because a design can keep the motif atoms globally close while burying, rotating, or occluding the antibody-facing surface.

## Decision Policy

Do not start RFD3 Phase 2 production for the current site V benchmark. The contact-core pilot did not produce contact-face pass candidates, and the discontinuous/contact-derived condition is still blocked by auditable wrapper support.

For the current benchmark, RFD3 should be positioned as a calibrated secondary backend for all-atom, contact-core, complex, and discontinuous-motif exploration. RFdiffusion v1 remains the default continuous-motif scaffold reproduction baseline.
