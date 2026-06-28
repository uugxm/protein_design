# Environment Notes

No base conda environment was modified.

## Reused Environments

| Name | Path | Use |
| --- | --- | --- |
| `rfdiffusion-se3nv` | `~/protein_design/envs/rfdiffusion-se3nv` | Symlink to existing RFdiffusion env under `~/protein-design/envs/rfdiffusion-se3nv`. |
| `pytorch/2.3.1` module | site module | Used for ProteinMPNN smoke test and templates. |

## Recommended Future Envs

Keep these separate:

- `ligandmpnn`
- `bindcraft`
- `rfantibody`
- `colabdesign-af2`
- `boltz`
- `antibody-tools`
- `structure-tools`

Do not combine RFdiffusion, ColabDesign/AF2, BindCraft, RFantibody, and PyRosetta in one environment.
