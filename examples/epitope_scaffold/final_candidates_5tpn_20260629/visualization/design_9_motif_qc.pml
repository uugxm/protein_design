reinitialize
load ../design_9/design_9_motif_only_aligned.pdb, reference_motif_aligned
load ../design_9/design_9_af3_model.pdb, af3_model
load ../design_9/design_9_rf3_model.pdb, rf3_model
load ../design_9/design_9_rfdiffusion_backbone.pdb, rfdiffusion_backbone
hide everything
show cartoon, af3_model or rf3_model or rfdiffusion_backbone
color gray80, af3_model
color marine, rf3_model
color wheat, rfdiffusion_backbone
show sticks, reference_motif_aligned
color yellow, reference_motif_aligned and chain R
color orange, reference_motif_aligned and chain A
color cyan, reference_motif_aligned and chain B
select motif_reference, reference_motif_aligned and chain R
select motif_af3_aligned, reference_motif_aligned and chain A
select motif_rf3_aligned, reference_motif_aligned and chain B
select local_support_af3, af3_model within 8 of motif_af3_aligned
select local_support_rf3, rf3_model within 8 of motif_rf3_aligned
show sticks, local_support_af3 or local_support_rf3
set cartoon_transparency, 0.45, af3_model
set cartoon_transparency, 0.35, rf3_model
set stick_radius, 0.16
zoom reference_motif_aligned, 12
set ray_opaque_background, off
png design_9_motif_qc.png, width=1800, height=1200, ray=1
