# 表位支架设计工作流培训手册

本文面向需要实际使用表位支架设计流程的研究人员。目标不是复现某个历史 benchmark，而是把一套可迁移的判断规则讲清楚：什么时候用 RFdiffusion v1，什么时候用 Foundry RFD3，怎样固定 motif，怎样用 ProteinMPNN/LigandMPNN 设计序列，以及怎样用 AF3、RF3 和可选 Boltz 做结构验证。

## 1. 表位支架设计解决什么问题

表位支架设计（epitope scaffolding）要解决的问题是：把一个已知结构中的关键表位、结合片段或功能 motif，嵌入一个新的、可表达、可展示、相对稳定的蛋白支架中。

它通常用于：

- 疫苗抗原设计：保留中和抗体识别的局部表位。
- 结合界面展示：把一段关键 loop、helix 或 strand 放到新的折叠背景中。
- 功能片段稳定化：让原本柔性的局部结构在新支架上被支撑。
- 展示库设计：为 phage display、yeast display 或其他筛选体系准备候选 scaffold。

它不直接证明免疫原性、亲和力或可表达性。计算流程只能给出结构假设和候选优先级，最后仍然需要实验验证。

## 2. 核心概念

motif / epitope：需要保留的结构片段，可以是一段连续残基，也可以是多段不连续残基。

reference structure：motif 的来源结构。必须记录结构来源、链、残基编号、是否有插入码、是否经过重编号。

contig：告诉 backbone generator 哪些区域是待生成支架，哪些区域是固定 motif。不同后端语法不同。

fixed atoms：被固定的原子集合。`BKBN` 表示固定 backbone 原子；`ALL` 表示固定所有重原子，通常用于 sidechain 对识别很关键的表位。

sequence design：backbone 生成后，用 ProteinMPNN 或 LigandMPNN 重新设计支架序列，同时保持 motif 残基不变或保持关键接触约束。

prediction validation：用 AF3、RF3、Boltz 等预测最终序列结构，检查 motif 是否还保持在正确几何构象中。

motif-specific QC：不是看整个蛋白像不像，而是重点看 motif 的 RMSD、原子覆盖、局部支撑、冲突、置信度和可及性。

## 3. 文本流程图

```text
结构来源和科学问题
  |
  v
定义 motif provenance
  - reference structure
  - chain/residue/insertion code
  - continuous or discontinuous
  - fixed atoms: BKBN or ALL
  |
  v
选择 backbone generator
  - RFdiffusion v1: 连续蛋白 motif 的默认生产基线
  - Foundry RFD3: all-atom/contact-aware/discontinuous/ligand/sidechain 场景
  |
  v
生成 backbone + motif mapping
  |
  v
序列设计
  - ProteinMPNN: 默认 protein-only
  - LigandMPNN: ligand/non-protein/contact-aware
  |
  v
预测验证
  - AF3: primary validator
  - RF3: independent confirmation
  - Boltz: optional warning, especially no-MSA mode
  |
  v
motif QC + confidence + clash + diversity
  |
  v
候选状态分级
  generated -> predicted -> validated_computational
  -> experimental_candidate -> cloning_ready
```

## 4. 工具选择表

| 任务场景 | 推荐工具 | 说明 |
| --- | --- | --- |
| 连续 protein motif，普通 backbone scaffolding | RFdiffusion v1 | 当前默认生产基线，简单、稳定、适合连续 contig |
| 不连续 motif | Foundry RFD3 | 不要把不连续 motif 强行拼成连续 contig |
| sidechain 几何很关键 | Foundry RFD3 + `ALL` fixed atoms | 例如抗体接触热点、配体接触侧链 |
| ligand、metal、cofactor、glycan、nucleic acid 相关设计 | Foundry RFD3 + LigandMPNN | 需要 all-atom/contact-aware 表达 |
| protein-only 序列设计 | ProteinMPNN | 默认选择，固定 motif 位置 |
| ligand 或非蛋白接触约束下的序列设计 | LigandMPNN | 用于 contact-aware sequence design |
| 主验证模型 | AF3 | 用于最终序列结构预测和 motif QC |
| 独立确认 | RF3 | 高优先级和边界候选建议加入 |
| 额外冲突信号 | Boltz | 可选；no-MSA 模式不建议作为硬过滤 |

## 5. RFdiffusion v1 参数要点

RFdiffusion v1 适合连续 motif。典型参数包括：

```bash
INPUT_PDB=/path/to/reference.pdb
CONTIGS='[20-60/A100-115/20-60]'
NUM_DESIGNS=20
OUTPUT_PREFIX=/path/to/run/rfdiffusion_outputs/design
```

解释：

- `INPUT_PDB` 是 motif 来源结构。
- `CONTIGS` 中 `20-60` 表示 N 端或 C 端支架长度范围，`A100-115` 表示链 A 的固定 motif。
- `NUM_DESIGNS` 是生成 backbone 数量。小试可以 4-10，生产模板常用 10-50。
- `OUTPUT_PREFIX` 决定输出 `.pdb` 和 `.trb` 的前缀。

注意事项：

- RFdiffusion v1 的 contig 是 slash-style，例如 `[20-60/A100-115/20-60]`。
- 它最适合连续 motif；不连续 motif 不应硬塞进一个连续区间。
- `.trb` mapping 很重要，后续固定 ProteinMPNN motif 位置和计算 motif RMSD 都依赖它。

## 6. Foundry RFD3 参数要点

Foundry RFD3 是 generation/design backend，不是 RF3 folding backend。它适合 all-atom、contact-aware、discontinuous、sidechain、ligand 或非蛋白上下文。

RFD3 的 contig 语法与 RFdiffusion v1 不同：

```text
RFdiffusion v1: [10-40/A100-115/10-40]
Foundry RFD3:  10-40,A100-115,10-40
```

典型 InputSpecification 片段：

```json
{
  "motif_scaffold": {
    "dialect": 2,
    "input": "/path/to/reference.pdb",
    "contig": "20-60,A100-115,20-60",
    "select_fixed_atoms": {
      "A100-115": "BKBN"
    },
    "is_non_loopy": true
  }
}
```

常见可记录参数：

| 参数 | 作用 |
| --- | --- |
| `input` | reference PDB/CIF |
| `contig` | RFD3 comma-separated contig，chain break 用 `/0` |
| `select_fixed_atoms` | 例如 `{ "A100-115": "BKBN" }` 或 `{ "A100-115": "ALL" }` |
| `select_unfixed_sequence` | 指定允许重新设计的序列区域 |
| `length` | 总长度约束 |
| `is_non_loopy` | conditioning flag |
| `partial_t` | partial diffusion 噪声强度 |
| `inference_sampler.num_timesteps` | 采样步数 |
| `diffusion_batch_size` / `n_batches` | 采样批次设置 |

`BKBN` 与 `ALL` 的选择：

- `BKBN`：只固定 backbone，适合 backbone 几何是主要约束、sidechain 可由设计重新优化的场景。
- `ALL`：固定所有重原子，适合 sidechain 是表位或配体接触核心的一部分。

## 7. ProteinMPNN 与 LigandMPNN

ProteinMPNN 是 protein-only scaffold sequence design 的默认选择。输入通常包括 backbone PDB、motif mapping、固定位置 JSONL，以及采样参数。

推荐默认：

```bash
NUM_SEQ=4
TEMP=0.1
```

含义：

- `NUM_SEQ`：每个 backbone 生成多少条序列。早期筛选可用 4，想增加多样性可用 8。
- `TEMP`：采样温度。`0.1` 更保守，较高温度增加多样性但也可能增加不稳定序列。
- motif 位置应固定，除非用户明确要求探索 motif 变体。

LigandMPNN 用于：

- ligand、cofactor、metal、glycan、nucleic acid 接触区域。
- 需要保留非蛋白接触几何的设计。
- 需要 contact-aware sequence design 的场景。

不要把 ligand/contact-aware 问题简化成普通 ProteinMPNN，除非明确说明这是临时近似。

## 8. AF3、RF3、Boltz 验证

AF3 是 primary validator。它用于检查最终序列是否能折回目标支架，并检查 motif 是否保持。

RF3 是 independent confirmation。对于要推进的候选，建议用 RF3 复核 AF3 结果，尤其是：

- AF3 分数好但 motif 边界或局部支撑可疑。
- 候选准备进入实验 shortlist。
- 不同 fold cluster 中需要选代表。

Boltz 是 optional warning signal。尤其是 no-MSA single-sequence 模式，可能对 de novo motif scaffold 给出严重偏离的结果。除非已经用 MSA/template-enabled 输入在当前问题上校准过，否则不要把 Boltz no-MSA 当作硬过滤。

重要输入规则：

- RF3 和 Boltz 输入必须从 canonical sequence/structure manifest 或各自 adapter 生成。
- 不要把 AF3 stage/output 中的 `*_data.json` 当作 RF3 或 Boltz 输入。

## 9. Motif-specific QC

候选不能只看 global pLDDT 或 raw motif RMSD。至少检查：

| QC 项 | 推荐解释 |
| --- | --- |
| motif RMSD | predicted model 中 motif 对 reference motif 的 RMSD |
| atom coverage | 参与 RMSD 的原子数量；缺原子时 RMSD 不可信 |
| sidechain RMSD | `ALL` fixed atoms 或 sidechain-critical motif 必看 |
| pLDDT | 全局和 motif-local 置信度都要看 |
| PAE | motif 与支架之间相对定位是否可信 |
| clash count | motif 周围和整体结构冲突 |
| missing residues | motif 或支撑区域是否缺失 |
| local support | motif 6-10 Angstrom 范围内是否有合理支撑 |
| accessibility | 表位是否暴露给抗体、受体或筛选体系 |

常用阈值起点：

```text
MIN_PLDDT=70
MAX_PAE=10
MAX_MOTIF_RMSD=1.5-2.5 Angstrom
MAX_CLASHES=20
```

阈值不是绝对真理。紧凑连续 epitope 可更严格；柔性 loop 或复杂 contact-aware 场景需要结合结构检查和实验目的调整。

## 10. Phage display QC

如果候选要用于 phage display，需要额外检查：

- motif 是否暴露，不能被 scaffold 埋住。
- N/C termini 是否适合 display fusion。
- 是否有不必要 cysteine、潜在错误二硫键或过强疏水 patch。
- 是否有 stop codon、非标准氨基酸、异常低复杂度。
- linker 与 display platform 是否兼容。
- 序列长度是否适合合成、克隆和展示。
- library 设计是否有明确多样性策略。

只有在表达系统、vector、tag/fusion、linker、codon optimization、克隆策略和命名规则都确定后，才能称为 `cloning_ready`。

## 11. 推荐默认设置

通用 protein-only 连续 motif：

```text
backbone backend: RFdiffusion v1
sequence backend: ProteinMPNN
NUM_DESIGNS: 20
NUM_SEQ: 4
TEMP: 0.1
primary predictor: AF3
confirmation: RF3 for promoted candidates
Boltz: optional warning only
fixed atoms: BKBN
```

sidechain/contact-aware 或不连续 motif：

```text
backbone backend: Foundry RFD3
sequence backend: LigandMPNN if non-protein/contact-aware, otherwise ProteinMPNN
fixed atoms: ALL for sidechain-critical motif, otherwise BKBN
primary predictor: AF3
confirmation: RF3
Boltz: optional, not hard gate without calibration
```

## 12. 常见错误

把 RF3 当成 backbone generator：错误。`foundry_rf3` 是 folding/prediction backend；`foundry_rfd3` 才是 RFD3 backbone generation backend。

把不连续 motif 塞进连续 contig：错误。应使用 Foundry RFD3 或其他能表达不连续选择的 contact-aware 方法。

只看 raw motif RMSD 就推进候选：错误。raw backbone RMSD 只是生成诊断，必须看 AF3/RF3 predicted structure 中的 motif QC。

用 AF3 `*_data.json` 喂给 RF3/Boltz：错误。RF3/Boltz 应使用 canonical manifest 或各自 adapter 生成输入。

没有表达/vector/tag/codon 策略就说 cloning-ready：错误。最多只能说 experimental candidate 或 computationally validated candidate。

忽略 motif provenance：错误。没有清楚的 reference、chain、residue 和 fixed atom policy，后续 RMSD 和实验解释都会失去依据。

## 13. 最小通用例子

假设我们有一个 reference 结构 `reference.pdb`，要保留链 A 的 100-115 残基作为连续 protein motif。

motif TSV：

```text
chain	start	end	label	fixed_atoms
A	100	115	target_epitope	BKBN
```

RFdiffusion v1 backbone 生成：

```bash
INPUT_PDB=/path/to/reference.pdb \
CONTIGS='[20-60/A100-115/20-60]' \
NUM_DESIGNS=20 \
OUTPUT_PREFIX=/path/to/run/rfdiffusion_outputs/design \
  sbatch scripts/slurm_templates/run_rfdiffusion_epitope.sbatch
```

生成 backbone list：

```bash
find /path/to/run/rfdiffusion_outputs -maxdepth 1 -name '*.pdb' | sort > /path/to/run/backbone_list.txt
```

ProteinMPNN：

```bash
TASK_LIST=/path/to/run/backbone_list.txt \
WORK_ROOT=/path/to/run/array_work \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=mpnn \
NUM_SEQ=4 \
TEMP=0.1 \
  sbatch --array=1-20 scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

AF3 验证：

```bash
TASK_LIST=/path/to/run/backbone_list.txt \
WORK_ROOT=/path/to/run/array_work \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=predict \
PREDICTOR=af3 \
PREDICT_MAX_RECORDS=1 \
PREDICT_SKIP_FIRST=1 \
  sbatch --array=1-20 scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

QC 过滤：

```bash
TASK_LIST=/path/to/run/backbone_list.txt \
WORK_ROOT=/path/to/run/array_work \
REFERENCE_PDB=/path/to/reference.pdb \
MOTIF_TSV=/path/to/motif_residues.tsv \
STAGE=filter \
MIN_PLDDT=70 \
MAX_PAE=10 \
MAX_MOTIF_RMSD=2.0 \
MAX_CLASHES=20 \
  sbatch --array=1-20 scripts/slurm_templates/run_epitope_scaffold_array.sbatch
```

## 14. 输出解读

候选状态建议使用以下分级：

| 状态 | 含义 |
| --- | --- |
| `generated` | backbone 已生成，但序列设计和预测 QC 不完整 |
| `predicted` | 至少一个预测器已完成 |
| `validated_computational` | motif、confidence、clash、cross-model 证据通过 |
| `experimental_candidate` | 适合实验评审，但还未完成克隆策略 |
| `cloning_ready` | 表达、vector、tag/linker、codon、克隆策略均已确定 |

ranking 时建议综合：

1. AF3 motif RMSD 和 motif-local confidence。
2. RF3 是否独立确认。
3. PAE 和 clash count。
4. motif 周围支撑和可及性。
5. sequence liabilities。
6. fold/sequence diversity。
7. 与实验体系的兼容性。

不要把 `top_designs.csv` 中的排名理解为“可以直接下单”。它只是计算优先级，需要再经过实验构建规则审查。

## 15. 参考资料与内部文档

- Functional site scaffolding: Wang et al., scaffolding protein functional sites using deep learning.
- RFdiffusion: Watson et al., de novo design of protein structure and function with RFdiffusion.
- ProteinMPNN: Dauparas et al., robust deep learning-based protein sequence design.
- LigandMPNN: RosettaCommons LigandMPNN documentation and current release notes for ligand/non-protein-aware inverse folding.
- AlphaFold 3: Abramson et al., accurate structure prediction of biomolecular interactions.
- Foundry / RFdiffusion3 / RF3: RosettaCommons Foundry documentation, RFdiffusion3 model notes, RF3 folding notes, AtomWorks/RF3 release notes, and installed backend reports.
- Boltz: Boltz documentation and model reports; use as optional cross-model signal unless calibrated for the current MSA/template setting.
- Chai: Chai model documentation and model reports if a workflow enables Chai as an additional predictor.
- Repository docs: `docs/foundry_rfd3_backend_report.md`, `docs/rf3_backend_report.md`, `docs/final_candidate_selection_report.md`, and the reusable skill at `skills/epitope_scaffold_design/SKILL.md`.

## 16. 历史经验边界

历史 benchmark 可以提供经验，例如连续 protein motif 上 RFdiffusion v1 可能是稳定基线，Foundry RFD3 对复杂场景更有表达能力，Boltz no-MSA 可能与 AF3/RF3 出现严重冲突。但这些都不能变成硬编码路径或固定结论。

每个新项目都必须重新记录 motif provenance、backend choice、fixed atom policy、sampler parameters、prediction settings 和 QC thresholds。
