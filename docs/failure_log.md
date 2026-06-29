# Failure Log

Date: 2026-06-28

## GitHub Repository Clone Failures

GitHub homepage was reachable by `curl -I`, but repository `ls-remote`/clone was unstable from TYL. These modules were not installed:

```bash
git clone --depth=1 https://github.com/dauparas/LigandMPNN ~/protein_design/repos/LigandMPNN
git clone --depth=1 https://github.com/martinpacesa/BindCraft ~/protein_design/repos/BindCraft
git clone --depth=1 https://github.com/RosettaCommons/RFantibody ~/protein_design/repos/RFantibody
git clone --depth=1 https://github.com/sokrypton/ColabDesign ~/protein_design/repos/ColabDesign
```

Observed symptoms included `Empty reply from server`, timeout, or failed `ls-remote`.

Update at 2026-06-28 16:54 Asia/Shanghai: added `~/protein_design/scripts/clone_with_github_mirrors.sh`, which tries direct GitHub first and then mirror/proxy URLs. On this retry, direct GitHub recovered before mirror fallback was needed, and all source repositories cloned successfully. Repository commits are recorded in `docs/repo_commits.tsv`; raw clone logs are not tracked.

## HuggingFace

`curl -I https://huggingface.co` timed out after 8 seconds. Avoid deployment plans that require live HuggingFace downloads from compute jobs; stage model weights through an approved route or use site containers.

## RFdiffusion GLIBCXX

`run_inference.py` failed without the env libstdc++:

```text
ImportError: /lib64/libstdc++.so.6: version `GLIBCXX_3.4.26' not found
```

Fix used in templates:

```bash
export LD_LIBRARY_PATH=~/protein_design/envs/rfdiffusion-se3nv/lib:$LD_LIBRARY_PATH
```
