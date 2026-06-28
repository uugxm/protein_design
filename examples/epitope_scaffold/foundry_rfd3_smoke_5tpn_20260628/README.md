# Foundry RFD3 5TPN Smoke Test

Date: 2026-06-28

Purpose: verify that `foundry_rfd3` can generate a 5TPN motif scaffold and feed
the existing ProteinMPNN -> AF3 -> filter/ranking pipeline.

```text
Motif: 5TPN chain A residues 163-181
RFD3 contig: 10-40,A163-181,10-40
Motif sequence: EVNKIKSALLSTNKAVVSL
Backbone job: 123264
ProteinMPNN job: 123265
AF3 job: 123266
Filter job: 123267
Merge job: 123268
Result: end-to-end completed, filter FAIL
pLDDT mean: 71.91
PAE mean: 18.22
Motif RMSD: 7.62
Clash count: 0
```

Important outputs:

```text
foundry_rfd3/input.json
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
reports/all_filter_summary.csv
reports/top_designs.csv
reports/run_report.json
logs/
```

The failing filter result is expected for this single smoke design; the purpose
of the run is interface validation, not design selection.
