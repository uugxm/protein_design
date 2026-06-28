# Backend Comparison

| backend | backbone_success_rate | proteinmpnn_success_rate | af3_prediction_success_rate | filter_pass_rate | plddt_mean_mean | pae_mean_mean | motif_rmsd_mean | clash_count_mean | top_backbone_id | top_design_id | top_pass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| rfdiffusion_v1 | 1.0000 | 1.0000 | 1.0000 | 0.9000 | 83.6895 | 4.3982 | 1.2157 | 0.1000 | design_3 | design_3 | PASS |
| rfdiffusion_all_atom | 1.0000 | 1.0000 | 1.0000 | 0.0000 | 88.8509 | 7.0484 | 6.5673 | 0.0000 | design_8 | design_8 | FAIL |

Ranking in each backend uses pLDDT descending, PAE ascending, motif RMSD ascending, and clash_count ascending.
