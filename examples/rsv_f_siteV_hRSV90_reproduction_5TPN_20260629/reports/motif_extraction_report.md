# Motif Extraction Report

## Inputs

- complex: `/public/home/yinyifan/protein_design/examples/rsv_f_siteV_hRSV90_reproduction_5TPN_20260629/inputs/5TPN.pdb`
- antigen_chain: `A`
- antibody_heavy_chain: `H`
- antibody_light_chain: `L`
- heavy_atom_contact_cutoff_angstrom: `5.00`
- whitelist: ``
- blacklist: ``

## Epitope

- residue_count: `21`
- residue_list: `A169,A170,A171,A172,A173,A174,A175,A176,A177,A178,A188,A191,A194,A196,A197,A200,A201,A226,A262,A263,A271`
- residue_sequence: `SALLSTNKAVLKDKNDKKNDK`
- segmentation: `169-178,188-188,191-191,194-194,196-197,200-201,226-226,262-263,271-271`
- continuity: `discontinuous`
- heavy_chain_contact_count: `252`
- light_chain_contact_count: `224`
- total_atom_contact_count: `476`
- buried_surface_proxy: heavy atom contact count and contacted antibody residue count only; true BSA not computed
- warning: `motif_is_fragmented_more_than_3_segments`

## Comparison With Previous Test Motif A163-181

- overlap_residues: `A169,A170,A171,A172,A173,A174,A175,A176,A177,A178`
- current_only_residues: `A188,A191,A194,A196,A197,A200,A201,A226,A262,A263,A271`
- previous_only_residues: `A163,A164,A165,A166,A167,A168,A179,A180,A181`

## Recommendation

Use this contact-derived motif for benchmark only after comparing contact4/contact5 and RFdiffusion original A163-181 references. Prefer the smaller contact4 set when it captures the same key site-V residues; use contact5 if contact4 is too sparse.

## Contact Residues

| residue | aa | min_distance | heavy_contacts | light_contacts | antibody_contact_residues |
| --- | --- | ---: | ---: | ---: | --- |
| A169 | S | 3.095 | 10 | 3 | H64;L109;L110 |
| A170 | A | 2.885 | 0 | 16 | L107;L108;L109 |
| A171 | L | 4.036 | 4 | 0 | H109 |
| A172 | L | 3.322 | 26 | 28 | H107;H109;H64;L110 |
| A173 | S | 2.521 | 34 | 38 | H107;H109;H113;H40;L107;L110;L112 |
| A174 | T | 2.715 | 52 | 33 | H109;H113;L107;L108;L38 |
| A175 | N | 2.938 | 41 | 4 | H109;H112A;H113;L38 |
| A176 | K | 2.839 | 0 | 9 | L108;L37;L38 |
| A177 | A | 3.233 | 0 | 20 | L108;L36;L38 |
| A178 | V | 2.770 | 0 | 33 | L108;L109;L28;L36 |
| A188 | L | 3.628 | 0 | 4 | L36 |
| A191 | K | 3.276 | 7 | 0 | H109;H111;H112A |
| A194 | D | 2.278 | 21 | 0 | H111;H111A |
| A196 | K | 4.882 | 2 | 0 | H59 |
| A197 | N | 3.900 | 11 | 0 | H111;H111A;H58 |
| A200 | D | 4.424 | 4 | 0 | H58 |
| A201 | K | 3.148 | 35 | 0 | H110;H36;H58 |
| A226 | K | 3.665 | 5 | 0 | H111A;H112C |
| A262 | N | 4.399 | 0 | 1 | L83 |
| A263 | D | 3.074 | 0 | 34 | L36;L37;L83 |
| A271 | K | 4.956 | 0 | 1 | L83 |
