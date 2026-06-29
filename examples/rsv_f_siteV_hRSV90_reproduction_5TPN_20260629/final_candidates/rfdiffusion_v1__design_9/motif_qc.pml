load motif_aligned.pdb, motif_reference
load af3_model.pdb, af3_model
load rf3_model.pdb, rf3_model
load backbone.pdb, backbone
hide everything
show cartoon, af3_model or rf3_model or backbone
show sticks, motif_reference
color gray70, backbone
color marine, af3_model
color orange, rf3_model
color yellow, motif_reference
zoom motif_reference
