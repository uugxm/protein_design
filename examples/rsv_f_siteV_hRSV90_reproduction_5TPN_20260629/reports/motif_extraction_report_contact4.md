# Motif Extraction Report

## Inputs

- complex: `/public/home/yinyifan/protein_design/examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/inputs/5TPN.pdb`
- antigen_chain: `A`
- antibody_heavy_chain: `H`
- antibody_light_chain: `L`
- heavy_atom_contact_cutoff_angstrom: `4.00`
- whitelist: ``
- blacklist: ``

## Epitope

- residue_count: `16`
- residue_list: `A169,A170,A172,A173,A174,A175,A176,A177,A178,A188,A191,A194,A197,A201,A226,A263`
- residue_sequence: `SALSTNKAVLKDNKKD`
- segmentation: `169-170,172-178,188-188,191-191,194-194,197-197,201-201,226-226,263-263`
- continuity: `discontinuous`
- heavy_chain_contact_count: `72`
- light_chain_contact_count: `72`
- total_atom_contact_count: `144`
- buried_surface_proxy: heavy atom contact count and contacted antibody residue count only; true BSA not computed
- warning: `motif_is_fragmented_more_than_3_segments`

## Comparison With Previous Test Motif A163-181

- overlap_residues: `A169,A170,A172,A173,A174,A175,A176,A177,A178`
- current_only_residues: `A188,A191,A194,A197,A201,A226,A263`
- previous_only_residues: `A163,A164,A165,A166,A167,A168,A171,A179,A180,A181`

## Recommendation

Use this contact-derived motif for benchmark only after comparing contact4/contact5 and RFdiffusion original A163-181 references. Prefer the smaller contact4 set when it captures the same key site-V residues; use contact5 if contact4 is too sparse.

## Contact Residues

| residue | aa | min_distance | heavy_contacts | light_contacts | antibody_contact_residues |
| --- | --- | ---: | ---: | ---: | --- |
| A169 | S | 3.095 | 3 | 0 | H64 |
| A170 | A | 2.885 | 0 | 3 | L108;L109 |
| A172 | L | 3.322 | 7 | 7 | H109;H64;L110 |
| A173 | S | 2.521 | 10 | 9 | H107;H109;L107;L110 |
| A174 | T | 2.715 | 16 | 14 | H109;H113;L107;L38 |
| A175 | N | 2.938 | 12 | 1 | H109;H113;L38 |
| A176 | K | 2.839 | 0 | 4 | L38 |
| A177 | A | 3.233 | 0 | 8 | L108;L38 |
| A178 | V | 2.770 | 0 | 12 | L108;L109;L36 |
| A188 | L | 3.628 | 0 | 1 | L36 |
| A191 | K | 3.276 | 1 | 0 | H111 |
| A194 | D | 2.278 | 10 | 0 | H111;H111A |
| A197 | N | 3.900 | 1 | 0 | H111 |
| A201 | K | 3.148 | 11 | 0 | H36;H58 |
| A226 | K | 3.665 | 1 | 0 | H111A |
| A263 | D | 3.074 | 0 | 13 | L36;L37;L83 |
