load design_9_boltz_motif_aligned.pdb, aligned_motif
load ../../predictions_flat/boltz/design_9_T_0.1_sample_4_score_1.1683_global_score_1.4381_seq_recovery_0.0250.pdb, boltz_full_model
hide everything
show sticks, aligned_motif
color green, chain R
color magenta, chain M
show cartoon, boltz_full_model
set cartoon_transparency, 0.65, boltz_full_model
zoom aligned_motif
