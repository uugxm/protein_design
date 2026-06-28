# RFDiffusionAA 5TPN Smoke Test

This is the compact artifact bundle for the first working
`rfdiffusion_all_atom` smoke test in the protein design stack.

## Run

```text
Cluster run directory: /public/home/yinyifan/protein_design/examples/epitope_scaffold/rfdiffusion_all_atom_smoke_5tpn_20260628_194145
Slurm job: 123174
Node: gpu14
State: COMPLETED
Elapsed: 00:01:52
Backend: rfdiffusion_all_atom via BACKBONE_BACKEND=rf3
Input motif: 5TPN chain A residues 163-181
RFDiffusionAA contig: ["10-40,A163-181,10-40"]
```

## Outputs

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
logs/backbone_gen-123174.out
logs/backbone_gen-123174.err
parse_check/parsed_pdbs.jsonl
parse_check/fixed_positions.jsonl
```

RFDiffusionAA denoising completed, but upstream ligand-free idealization raised
`AssertionError: Found >1 ligand: []`. The stack fallback copied the unidealized
PDB to the normalized output path and generated motif mapping with
`scripts/make_motif_mapping_from_sequence.py`.

Validation summary:

```text
ProteinMPNN parse_multiple_chains.py parsed 1 PDB.
make_fixed_positions_jsonl.py --strict succeeded.
Fixed motif positions: A38-A56
Reference mapping: 5TPN A163-A181 -> generated A38-A56
```
