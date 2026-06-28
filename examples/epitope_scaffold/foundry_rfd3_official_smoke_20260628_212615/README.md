# Foundry RFD3 Official Smoke Test

Date: 2026-06-28

Purpose: verify the official Foundry RFD3 CLI, checkpoint registry, CUDA runtime,
and example input before connecting RFD3 to the stack launcher.

```text
Slurm job: 123263
Node: gpu18
Runtime: /public/home/yinyifan/protein_design/envs/foundry-rfd3
Torch: 2.6.0+cu124
GPU: NVIDIA GeForce RTX 3090
Input: /public/home/yinyifan/protein_design/repos/foundry/models/rfd3/docs/examples/demo.json
Command: rfd3 design out_dir=<run_dir> inputs=<demo.json> skip_existing=False prevalidate_inputs=True diffusion_batch_size=1 n_batches=1 inference_sampler.num_timesteps=10
Result: completed
Outputs: 3 .cif.gz structures plus JSON metadata
```

This test does not use the epitope scaffold adapter. It only confirms the
official Foundry RFD3 entry point is usable on TYL.
