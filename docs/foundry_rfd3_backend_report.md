# Foundry RFD3 Backend Report

Foundry RFD3 is the supported all-atom/contact-aware backbone-generation backend
for this stack. RFdiffusion v1 remains the stable baseline for continuous motif
scaffolding. Foundry RF3 is a folding/prediction backend only.

## Source And Runtime

```text
Repository: https://github.com/RosettaCommons/foundry
Inspected commit: 62eba661f809120f0c5b3776837c61463e554c4c
Package: rc-foundry 0.2.0
Python: 3.12.13
Torch: 2.6.0+cu124 after CUDA 12.4 repair
Checkpoint directory: ~/protein_design/weights/foundry
RFD3 checkpoint: rfd3_latest.ckpt
```

The active TYL runtime is an isolated micromamba environment:

```text
~/protein_design/envs/foundry-rfd3
```

Installation template:

```bash
sbatch scripts/slurm_templates/install_foundry_micromamba.sbatch
```

CUDA repair template:

```bash
sbatch scripts/slurm_templates/repair_foundry_torch_cuda124.sbatch
```

The Docker/Apptainer route remains a fallback for sites with a local image
mirror:

```bash
sbatch scripts/slurm_templates/install_foundry_container.sbatch
```

## Stack Naming

```text
rfdiffusion_v1     stable RFdiffusion backbone generator
foundry_rfd3       Foundry RFdiffusion3 design/generation backend
foundry_rf3        Foundry folding/prediction backend
```

## Input Policy

Do not force RFdiffusion v1 contig assumptions onto RFD3. Generate RFD3-native
input with:

```bash
python scripts/make_rfd3_motif_input.py --help
python scripts/validate_rfd3_motif_input.py --help
```

For epitope/contact-aware scaffolding, prefer `FOUNDRY_RFD3_FIXED_ATOMS=ALL`
when sidechain/contact geometry must be preserved. Use `BKBN` only for
backbone-only debugging or ablation.

## Output Contract

The unified launcher normalizes RFD3 outputs to the same downstream contract as
RFdiffusion v1:

```text
rfdiffusion_outputs/design_0.pdb
rfdiffusion_outputs/design_0.trb
backbone_list.txt
run_params.json
backend_logs/backend.env
```

Runtime raw Foundry outputs are ignored by git.

## Historical Conclusion

Pilot smoke tests showed that Foundry RFD3 can run on TYL after the CUDA 12.4
torch repair and can feed the existing ProteinMPNN -> AF3 -> filter pipeline.
It remains experimental and should be compared side by side with RFdiffusion v1
before promotion for a new motif class.
