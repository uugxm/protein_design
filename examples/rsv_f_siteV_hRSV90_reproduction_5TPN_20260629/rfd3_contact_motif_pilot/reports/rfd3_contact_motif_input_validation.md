# RFD3 Contact Motif Input Validation

| condition | status | gpu | motif | segments | selected atoms | reason |
| --- | --- | --- | --- | --- | ---: | --- |
| c04_contact_core_a169_178_all_20_30 | valid_ready_to_run | yes | A169-178_contact_core | A169-178 | 69 |  |
| c05_discontinuous_contact_unindex_all | hold_not_cleanly_supported_in_current_wrapper | no | contact4_discontinuous_siteV | A169-170,A172-178,A188,A191,A194,A197,A201,A226,A263 | 120 | current_normalize_foundry_rfd3_outputs_requires_exact_concatenated_motif_sequence_for_trb_mapping |

Validation separates Foundry input syntax from current downstream wrapper support.
A condition may be expressible by Foundry but held if normalized PDB/TRB/fixed-position mapping cannot be audited cleanly.
