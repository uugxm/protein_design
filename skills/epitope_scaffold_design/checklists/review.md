# Epitope Scaffold Review Checklist

- Chain mapping checked against source PDB/mmCIF author and label IDs.
- Motif provenance checked and recorded in the motif TSV or report.
- Original RFdiffusion motif definition reconciled when running a reproduction benchmark.
- RFdiffusion v1 and Foundry RFD3 run on the same motif input.
- AF3 and RF3 inputs generated from the canonical sequence/structure layer.
- No AF3 `*_data.json` reused as RF3 or Boltz input.
- Boltz no-MSA result treated as warning only unless MSA/template-enabled validation was run.
- Pre-order QC completed before any cloning-ready construct table is generated.
- Generated artifacts are intentionally tracked or ignored.
- AF3 PASS count and motif RMSD distribution reviewed.
- RF3 confirmation reviewed for final primary candidates.
- Motif atoms missing is zero for selected candidates.
- Clash, NXS/T, low-complexity, and hydrophobic-stretch warnings reviewed.
- Fold, motif-local, and sequence clusters reviewed for diversity.
