<p align="center">
  <img src="docs/assets/fp-deerr-banner.png" alt="FP-DeErr: Application-Oriented Error Decomposition for Foundation Potentials" width="880">
</p>

<p align="center">
  <a href="https://mogroupumd.github.io/FP-DeErr/force-error.html"><b>Force Prediction</b></a>
  &nbsp;&middot;&nbsp;
  <a href="https://mogroupumd.github.io/FP-DeErr/phase-stability-ordering.html"><b>Phase Stability &amp; Ordering</b></a>
  &nbsp;&middot;&nbsp;
  <a href="https://mogroupumd.github.io/FP-DeErr/ion-migration-neb.html"><b>Ion Migration (NEB)</b></a>
</p>

# Overview

FP-DeErr applies application-oriented error decomposition to foundation potentials (FPs),
also known as universal machine-learning interatomic potentials (MLIPs), resolving where
errors arise in the computational tasks they are used for.

FP-DeErr introduces application-oriented error decomposition through metrics that resolve
performance according to the physically consequential quantities and configurations governing
computational tasks, including the fractions of highly accurate and large-force-error atoms,
far-from-equilibrium atoms, relative phase-stability and convex-hull agreement, and along-path
errors in ion migration. These error-decomposition metrics identify where FP errors arise
within specific computational tasks, providing targeted guidance for model development.

FP-DeErr provides the reference datasets, the evaluation code, and a public leaderboard for three
components: force prediction, phase stability and elemental ordering, and ion migration by NEB.

**Leaderboard: https://mogroupumd.github.io/FP-DeErr/**

**Paper: [arXiv:2609.05714](https://arxiv.org/abs/2609.05714)**

## Contents

- [Using FP-DeErr](#using-fp-deerr)
- [Quick start](#quick-start)
- [Benchmark components](#benchmark-components)
- [Repository structure](#repository-structure)
- [Foundation potentials evaluated](#foundation-potentials-evaluated)
  - [Evaluation matrix](#evaluation-matrix)
- [Contribute](#contribute)
- [Citation](#citation)
- [License](#license)

---

## Using FP-DeErr

FP-DeErr supports three modes of use.

- **Reported results.** The [leaderboard](https://mogroupumd.github.io/FP-DeErr/) gives the
  current metrics for every evaluated FP and requires no installation.
- **Evaluation of an additional potential.** The FP is registered in the relevant generator
  notebook and run against the provided reference datasets. See [Contribute](#contribute).
- **Application to an independent dataset.** The analysis functions in each component's
  `scripts/` directory accept standardized inputs directly.

All three components share a common workflow. Calculations are written to a standardized results
file, validated, and passed to the analysis functions that produce the reported metric tables. The
provided reference data and user-supplied data enter this workflow at the same point.

```text
        FP evaluated on the FP-DeErr reference data
                          or
            user DFT and FP results
                          |
                standardized results
                          |
               validation and analysis
                          |
                    metric tables
```

Each component documents its own workflow in detail.

- [Force prediction](Force_error/README.md#using-fp-deerr)
- [Phase stability and elemental ordering](Phase_stability_ordering/README.md#using-fp-deerr)
- [Ion migration by NEB](Ion_migration_NEB/README.md#using-fp-deerr)

---

## Quick start

The following example uses a five-structure subset of MatPES-PBE included in the repository and
requires no additional download.

```bash
git clone https://github.com/mogroupumd/FP-DeErr.git
cd FP-DeErr/Force_error
pip install -r requirements.txt
```

```python
import json, sys
from pathlib import Path

sys.path.insert(0, str(Path("scripts").resolve()))
from force_results import build_force_results

with open("examples/mace_matpes_cartesian_force_example.json") as f:
    example = json.load(f)

force_results = build_force_results(
    example["dft_forces"],
    {"mace": example["fp_forces"]},
    structure_ids=example["structure_ids"],
)

print("Models:", list(force_results))
print("Fields:", list(force_results["mace"]))
```

This is the standardization step underlying every force metric reported by FP-DeErr. The complete
tables and figures are produced by the analysis notebooks.

```bash
pip install jupyterlab
jupyter lab analysis/force_error_analysis_matpes_pbe.ipynb
```

---

## Benchmark components

**[Force prediction](Force_error/README.md)** compares FP and DFT forces atom by atom on
MatPES-PBE, MatPES-r2SCAN, and OMat24 rattled-1000. In addition to average MAE and RMSE, it
reports the fraction of highly accurate force predictions, joint force magnitude-angle accuracy,
large-force-error atoms, and errors on far-from-equilibrium atoms.
[Leaderboard](https://mogroupumd.github.io/FP-DeErr/force-error.html)

**[Phase stability and elemental ordering](Phase_stability_ordering/README.md)** evaluates whether
an FP reproduces the relative energies of competing phases, compositions, and elemental orderings,
using the FP-DeErr convex-hull and elemental-ordering benchmark subsets: 597 unique hull structures
across 22 ternary chalcogenide tie-line systems, and 305 elemental-ordering groups of 20
candidates each. It reports ground-state agreement, within-phase and global hull-minimum
agreement, Top-1 accuracy, Recall@k, Spearman rank correlation, and relaxation RMSD against the
DFT-relaxed structure.
[Leaderboard](https://mogroupumd.github.io/FP-DeErr/phase-stability-ordering.html)

**[Ion migration by NEB](Ion_migration_NEB/README.md)** applies the nudged elastic band method to
154 Li- and Na-ion migration pathways spanning 106 structurally distinct materials. It reports
non-converged FP-NEB calculations, forward and backward barrier errors, endpoint energy ranking
and energy-difference errors, energy-profile shape agreement, endpoint relaxation error, and
along-path force errors. Comparing the full FP-NEB workflow with static FP evaluations on the
DFT-NEB image structures separates intrinsic potential-energy-surface error from error introduced
by FP endpoint relaxation and pathway optimization.
[Leaderboard](https://mogroupumd.github.io/FP-DeErr/ion-migration-neb.html)

---

## Repository structure

```text
FP-DeErr/
├── README.md
├── ADDING_A_POTENTIAL.md             # how to register and run an additional FP
├── LICENSE
├── Force_error/                      # Force prediction
│   ├── README.md
│   ├── analysis/                     # analysis notebooks
│   ├── generation/                   # job generators (POTENTIAL_REGISTRY lives here)
│   ├── scripts/                      # importable metric and standardization functions
│   ├── data/                         # data documentation and download pointers
│   ├── examples/                     # small runnable examples, committed
│   └── requirements.txt
├── Phase_stability_ordering/         # same layout
├── Ion_migration_NEB/                # same layout, plus tests/
└── docs/                             # leaderboard website (GitHub Pages)
```

Large standardized data files are not committed to Git. Each component's `data/README.md` says
where to obtain them; the `examples/` slices need no download.

---

## Foundation potentials evaluated

These are the FPs currently on the leaderboard, with the exact checkpoints used. Model and
training-set sizes are the values recorded by this study's own code. As more FPs are tested they
are added here; existing results stay tied to the model version they were produced with and are
not silently replaced.

| FP | Model &amp; version | Model size | Training dataset | Approx. training-set size | Source |
|---|---|---|---|---|---|
| MACE | &gt;=v0.3.10 (MACE-MPA-0, medium) | 9.06M | MPTrj + sAlex | ~3.5M | [MACE foundation models](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html) |
| CHGNet | v0.3.0 | 412.5K | MPTrj | ~1.58M | [CHGNet](https://github.com/CederGroupHub/chgnet) |
| M3GNet | MP-2021.2.8-PES | 288.2K | MP-2021.2.8 | ~176.6K | [MatGL](https://matgl.ai/) |
| UMA | s-1p1 | 146.5M | OC20 + ODAC23 + OMat24 + OMC25 + OMol25 | ~500M | [FAIR Chemistry](https://fair-chem.github.io/) |
| M3GNet-MatPES | v2025.1 | 664.2K | MatPES-PBE | ~435K | [MatGL](https://matgl.ai/) &middot; [MatPES](https://matpes.ai/) |
| TensorNet-MatPES | v2025.1 | 837.9K | MatPES-PBE | ~435K | [MatGL](https://matgl.ai/) &middot; [MatPES](https://matpes.ai/) |
| MACE-MatPES | &gt;=v0.3.10 | 9.06M | Fine-tuned on MatPES-PBE* | ~435K | [MACE](https://github.com/acesuit/mace) |
| MACE-OMAT | &gt;=v0.3.10 (MACE-OMAT-0, medium) | 9.06M | OMat24, DFT (PBE+U)&para;&para; | not reported for this checkpoint | [MACE foundation models](https://mace-docs.readthedocs.io/en/latest/guide/foundation_models.html) |
| M3GNet-MatPES-r2SCAN | v2025.1 | 664.2K | MatPES-r2SCAN | ~388K | [MatGL](https://matgl.ai/) &middot; [MatPES](https://matpes.ai/) |
| TensorNet-MatPES-r2SCAN | v2025.1 | 837.9K | MatPES-r2SCAN | ~388K | [MatGL](https://matgl.ai/) &middot; [MatPES](https://matpes.ai/) |
| MACE-MatPES-r2SCAN | &gt;=v0.3.10 | 9.06M | Fine-tuned on MatPES-r2SCAN* | ~388K | [MACE](https://github.com/acesuit/mace) |
| Orb | orb-v3-conservative-inf-omat-20250404 | 25.5M | OMat24, AIMD subset only | ~55M&Dagger; | [Rhodes et al. 2025](https://arxiv.org/abs/2504.06231) |
| SevenNet | 7net-mf-ompa (modal `mpa`) | 25.7M | MPTrj + sAlex + OMat24, multi-fidelity; `mpa` selects the MPTrj + sAlex task | not reported for this checkpoint | [SevenNet pretrained models](https://sevennet.readthedocs.io/en/latest/user_guide/pretrained.html) &middot; [Kim et al. 2025](https://doi.org/10.1021/jacs.4c14455) |
| &#8627; SevenNet-0 | 7net-0 (SevenNet_0__11Jul2024) | 842.6K | MPTrj | ~1.58M | [SevenNet pretrained models](https://sevennet.readthedocs.io/en/latest/user_guide/pretrained.html) |
| &#8627; SevenNet-Nano | 7net-nano-6.0 | 103.4K | Distilled from 7net-Omni (`mpa` task) on 7net-Omni's training structures, including MatPES and OMat24&sect;&sect; | not reported | [SevenNet pretrained models](https://sevennet.readthedocs.io/en/latest/user_guide/pretrained.html) &middot; [SevenNet-Nano paper](https://arxiv.org/abs/2604.10887) |
| MatterSim | MatterSim-v1.0.0-5M | 4.55M | Nonpublic MatterSim active-learning dataset, GGA-PBE(+U)&dagger; | 6M | [Model card](https://github.com/microsoft/mattersim/blob/main/MODEL_CARD.md) &middot; [Yang et al. 2024](https://arxiv.org/abs/2405.04967) |
| &#8627; MatterSim-1M | MatterSim-v1.0.0-1M | 890.0K | Nonpublic MatterSim active-learning dataset, GGA-PBE(+U)&dagger; | 3M | [Model card](https://github.com/microsoft/mattersim/blob/main/MODEL_CARD.md) |
| Nequix | nequix-oam-1 | 707.6K | OMat24 + sAlex + MPTrj, DFT (PBE+U)&sect; | not reported for this checkpoint | [nequix repository](https://github.com/atomicarchitects/nequix) &middot; [Koker et al. 2025](https://arxiv.org/abs/2508.16067) |
| GPTFF | gptff_v2 | 502.5K | Atomly&#8214; | ~37.6M configurations | [Xie et al. 2024](https://doi.org/10.1016/j.scib.2024.08.039) |
| ALIGNN | alignnff_wt10 | 4.03M | JARVIS-DFT&para; | ~307.1K | [Choudhary et al. 2023](https://arxiv.org/abs/2209.05554) |
| NEP89 | nep89_20250409 | 976.3K | OMat24, MPTrj, SPICE, ANI-1xnr, SSE-ABACUS, SSE-VASP, Protein, UNEP-v1, CH, CHONPS, Water; mixed QM levels&dagger;&dagger; | 537,641 configurations | [GPUMD potentials](https://github.com/brucefan1983/GPUMD/tree/master/potentials/nep/nep89_20250409) &middot; [NEP89 paper](https://arxiv.org/abs/2504.21286) |
| DPA4 | DPA4-Plus-OMat24-v20260805 | 8.85M | OMat24, DFT / DFT+U&#35; | ~100.6M frames | [DPA4-OMat24 model card](https://huggingface.co/deepmodelingcommunity/DPA4-OMat24) |
| &#8627; DPA4-Air | DPA4-Air-OMat24-v20260805 | 5.15M | OMat24, DFT / DFT+U&#35; | ~100.6M frames | [DPA4-OMat24 model card](https://huggingface.co/deepmodelingcommunity/DPA4-OMat24) |
| GRACE | GRACE-3L-OMAT-large-ft-AM | 42.1M&Dagger;&Dagger; | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning | not reported for this checkpoint | [GRACE foundation models](https://gracemaker.readthedocs.io/en/latest/gracemaker/foundation/) |
| &#8627; GRACE-1L | GRACE-1L-OAM | 3.45M | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning | not reported for this checkpoint | [GRACE foundation models](https://gracemaker.readthedocs.io/en/latest/gracemaker/foundation/) &middot; [GRACE foundation-model paper](https://arxiv.org/abs/2508.17936) |
| &#8627; GRACE-2L | GRACE-2L-OAM | 12.6M | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning | not reported for this checkpoint | [GRACE foundation models](https://gracemaker.readthedocs.io/en/latest/gracemaker/foundation/) &middot; [GRACE foundation-model paper](https://arxiv.org/abs/2508.17936) |
| &#8627; GRACE-2L-large | GRACE-2L-OMAT-large-ft-AM | 26.4M | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning | not reported for this checkpoint | [GRACE foundation models](https://gracemaker.readthedocs.io/en/latest/gracemaker/foundation/) &middot; [GRACE foundation-model paper](https://arxiv.org/abs/2508.17936) |
| eqV2 | eqV2_31M_omat_mp_salex.pt | 31.2M | OMat24 pretraining &rarr; MPTrj + sAlex fine-tuning, DFT / DFT+U&#35; | not reported for this checkpoint | [Meta OMat24 models](https://huggingface.co/facebook/OMAT24) |
| eSEN | esen_30m_oam.pt | 30.2M | OMat24 pretraining &rarr; MPTrj + sAlex fine-tuning, DFT / DFT+U&#35; | not reported for this checkpoint | [Meta OMat24 models](https://huggingface.co/facebook/OMAT24) |
| NequIP-OAM-S | NequIP-OAM-S-0.1 | 616.4K | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning&#8214;&#8214; | ~113M frames (~101M + ~10.5M + ~1.5M) | [NequIP foundation potentials (Zenodo)](https://zenodo.org/records/18775904) |
| NequIP-OAM-M | NequIP-OAM-M-0.1 | 3.19M | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning&#8214;&#8214; | ~113M frames (~101M + ~10.5M + ~1.5M) | [NequIP foundation potentials (Zenodo)](https://zenodo.org/records/18775904) |
| NequIP-OAM-L | NequIP-OAM-L-0.1 | 9.61M | OMat24 pretraining &rarr; sAlex + MPTrj fine-tuning&#8214;&#8214; | ~113M frames (~101M + ~10.5M + ~1.5M) | [NequIP foundation potentials (Zenodo)](https://zenodo.org/records/18775904) |
| PET-OMat-XS | pet-omat-xs-v1.0.0 | 4.49M | OMat24, PBE&dagger;&dagger;&dagger; | not reported for this checkpoint | [UPET models](https://lab-cosmo.github.io/upet/latest/models.html) |
| PET-OMat-S | pet-omat-s-v1.0.0 | 25.9M | OMat24, PBE&dagger;&dagger;&dagger; | not reported for this checkpoint | [UPET models](https://lab-cosmo.github.io/upet/latest/models.html) |
| DPA-4.1C-Air | DPA-4.1C-Air-OAM | 433.7K | MPTrj + OMat24 + sAlex&Dagger;&Dagger;&Dagger; | not reported for this checkpoint | [DPA-4.1C-Air-OAM (figshare)](https://doi.org/10.6084/m9.figshare.34755132) |
| MACE-MH-1 | mace-mh-1 (head `omat_pbe`) | 6.44M | OMat24 pretraining &rarr; multi-head fine-tuning; `omat_pbe` head on an OMat24 replay set, PBE/PBE+U&sect;&sect;&sect; | 100M (pretraining) + fine-tuning sets&sect;&sect;&sect; | [MACE-MH-1 model card](https://huggingface.co/mace-foundations/mace-mh-1) |

\* Pre-trained on MACE-OMAT-0, then fine-tuned on the matched MatPES functional.

&dagger; The MatterSim model card reports "Training Data Size: 6M", "Model Parameters: 4.5M", and
training on "a specific variant of Density Functional Theory (PBE)". The GGA-PBE(+U) labelling,
with Hubbard U applied to selected materials following Materials Project settings, is described in
Yang et al. rather than on the model card. The dataset itself is not released, so the OOD label
reflects the absence of documented training exposure rather than a verified composition.
The same model card lists the smaller `MatterSim-v1.0.0-1M` checkpoint (MatterSim-1M) with
"Training Data Size: 3M" and "Model Parameters: 880K"; FP-DeErr counts 890,034 parameters in the
loaded checkpoint.

&Dagger; Rhodes et al. state that "all orb-v3-*-omat models are only trained on the AIMD subset of
OMat24", and that the OMat24 dataset "contains ~55 million AIMD-sampled structures".

&sect; The FP-DeErr checkpoint is `nequix-oam-1`. The official nequix repository documents this
checkpoint as trained on OMat24, sAlex and MPTrj at the DFT (PBE+U) level. The Nequix paper
describes an MPTrj-trained model and does not report a training-set size or parameter count for
this released OAM checkpoint; the 707,569-parameter model size shown here was measured from the
loaded checkpoint by FP-DeErr.

&#8214; GPTFF's Atomly labels were computed with VASP at the GGA-PBE level with a 520 eV
plane-wave cutoff and version 5.4 PAW pseudopotentials. The functional matches the FP-DeErr
reference; the cutoff and pseudopotential version do not necessarily, so small systematic
offsets relative to MatPES-PBE are expected independently of model quality.

&para; ALIGNN is trained on JARVIS-DFT at the **OptB88vdW** level, not PBE. Its training set is 307,113 points, split 90:5:5. It is the only FP here
trained entirely at a single functional other than the evaluation reference, so its scores measure
agreement with the FP-DeErr MatPES-PBE reference rather than a functional-matched fitting error.

&dagger;&dagger; NEP89 is trained on eleven datasets computed at different quantum-mechanical levels
rather than a single reference functional. Its FP-DeErr MatPES-PBE scores therefore measure
practical agreement with the PBE benchmark reference rather than agreement with a single matched
reference functional. The eleven datasets and the 537,641-configuration total are reported in the NEP89 paper;
the 976,331 trainable parameters were counted from the released model by FP-DeErr.

&Dagger;&Dagger; FP-DeErr counts 42.1M parameters (42,112,223) for the GRACE potential used in inference. The
released SavedModel additionally contains a 23.4M-parameter GMM uncertainty head that is disabled
in FP-DeErr runs and is therefore not included in the reported model size. The GRACE documentation
does not publish a parameter count; 42.1M was measured from the released model by FP-DeErr.

&#35; The immediate model sources describe these labels as DFT and DFT+U total-energy labels.
OMat24 itself uses PBE/PBE+U reference calculations; see the
[OMat24 dataset reference](https://arxiv.org/abs/2410.12771).

&sect;&sect; SevenNet-Nano is distilled from 7net-Omni: structures from 7net-Omni's training
databases, including MatPES, MatPES-r2SCAN, OMat24, MPTrj and Alexandria, were relabelled with
7net-Omni's `mpa` (PBE) task ([arXiv:2604.10887](https://arxiv.org/abs/2604.10887)). The paper
reports 105k parameters and does not report the size of the distillation set; FP-DeErr counts
103,401 parameters in the loaded checkpoint.

&para;&para; MACE-OMAT is the `mace-omat-0-medium` checkpoint (MACE-OMAT-0). The MACE foundation-model documentation lists it as trained on OMat24 at the DFT (PBE+U) level with VASP 54 pseudopotentials, released under the Academic Software License (ASL). It is the base model that the MACE-MatPES checkpoints were fine-tuned from (\*). FP-DeErr counts 9,063,204 parameters in the loaded checkpoint, the same as MACE-MPA-0 and MACE-MatPES. It was added to the leaderboards after the manuscript and is not part of the manuscript roster.

&#8214;&#8214; NequIP-OAM-S, -M and -L are the version 0.1 checkpoints of the [NequIP OAM release](https://zenodo.org/records/18775904). The release states that they are pre-trained on OMat24 (~101M frames) and fine-tuned on sAlex (~10.5M frames) and MPTrj (~1.5M frames); it does not state the DFT level of the labels. The model pages list 0.6M, 3.2M and 9.6M parameters; FP-DeErr counts 616,360, 3,189,672 and 9,605,688 in the loaded checkpoints. The weights are released under CC-BY-4.0. They were added to the leaderboards after the manuscript and are not part of the manuscript roster.

&dagger;&dagger;&dagger; PET-OMat-XS and PET-OMat-S are the v1.0.0 checkpoints of the PET-OMat family. The [UPET documentation](https://lab-cosmo.github.io/upet/latest/models.html) lists PET-OMat as trained on OMat24 at the PBE level, and the UPET paper ([arXiv:2601.16195](https://arxiv.org/abs/2601.16195)) reports 4.5M and 25.9M parameters; FP-DeErr counts 4,487,962 and 25,924,122. Neither source reports the number of training structures for these checkpoints. The UPET repository is released under the BSD-3-Clause license. They were added to the leaderboards after the manuscript and are not part of the manuscript roster.

&Dagger;&Dagger;&Dagger; DPA-4.1C-Air is the `DPA-4.1C-Air-OAM` checkpoint ([figshare](https://doi.org/10.6084/m9.figshare.34755132)). Its [Matbench Discovery model card](https://github.com/janosh/matbench-discovery/blob/main/models/deepmd/dpa-4.1c-air-oam.yml) describes it as trained on MPtrj, OMat24 and sAlex, with pre-training and fine-tuning, and lists 433,673 parameters, which matches the FP-DeErr count. It does not state which dataset was used in which stage, or the training-set size. The checkpoint is released under CC BY 4.0. It was added to the leaderboards after the manuscript and is not part of the manuscript roster.

&sect;&sect;&sect; MACE-MH-1 is a multi-head MACE model; FP-DeErr uses its default `omat_pbe` head (PBE/PBE+U). The [model card](https://huggingface.co/mace-foundations/mace-mh-1) describes pre-training on OMat24 (100M structures) followed by multi-head fine-tuning on a 10M OMat24 replay set (the `omat_pbe` head), MPTrj, SPICE-1, OC20, OMol (1%), RGD1 and MatPES-r2SCAN, each on its own head; the accompanying paper ([arXiv:2510.25380](https://arxiv.org/abs/2510.25380)) states that all weights, including the shared backbone, are fine-tuned. MatPES-PBE is not in its training data. The model card does not report a parameter count; FP-DeErr counts 6,439,878. It is released under the Academic Software License (ASL). It was added to the leaderboards after the manuscript and is not part of the manuscript roster.

&#8627; Rows marked with an arrow are additional checkpoints of the FP family directly above, at
a different model size. They are evaluated for Force Prediction (MatPES-PBE and OMat24
rattled-1000) only and appear on the Force Prediction leaderboard next to the family's main
checkpoint. The DPA4 sizes are the parameter counts published on the DPA4-OMat24 model card; the
other sizes are counted from the loaded checkpoints.

The manuscript revision expands the main roster to eleven FPs, adding Orb, MatterSim, DPA4
and GRACE to the seven originally reported. This website evaluates further FPs beyond that
manuscript roster: the Ion Migration (NEB) leaderboard currently lists 25 FPs and the Phase
Stability and Ordering leaderboard 25. The r2SCAN-trained entries are a separate set,
evaluated only on the MatPES-r2SCAN dataset. Model sizes are parameter counts measured from
the loaded checkpoints.

### Evaluation matrix

Which FPs were evaluated on which dataset. The parenthetical says whether that dataset is inside
the FP's own training data (`training`), outside it (`OOD`), a fine-tune of an OOD base model
onto it (`fine-tuned`), or a dataset used to pretrain the model before it was fine-tuned on
other data (`pretraining`).

| FP | MatPES-PBE (force) | OMat24 rattled-1000 (force, SI) | Phase stability / ordering | Ion migration (NEB) |
|---|---|---|---|---|
| MACE | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| CHGNet | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| M3GNet | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| UMA | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| M3GNet-MatPES | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| TensorNet-MatPES | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| MACE-MatPES | &#10003; (training) | &#10003; (pretraining)* | &#10003; (OOD) | &#10003; (OOD) |
| MACE-OMAT | &#10003; (OOD) | &#10003; (training)&para;&para; | &#10003; (OOD) | &#10003; (OOD) |
| Orb | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| SevenNet | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| &#8627; SevenNet-0 | &#10003; (OOD) | &#10003; (OOD) | not evaluated | not evaluated |
| &#8627; SevenNet-Nano | &#10003; (training) | &#10003; (training) | not evaluated | not evaluated |
| MatterSim | &#10003; (OOD)&dagger; | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| &#8627; MatterSim-1M | &#10003; (OOD)&dagger; | &#10003; (OOD) | not evaluated | not evaluated |
| Nequix | &#10003; (OOD)&sect; | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| GPTFF | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| ALIGNN | &#10003; (OOD)&para; | not evaluated | not evaluated | not evaluated |
| NEP89 | &#10003; (OOD)&dagger;&dagger; | &#10003; (OOD) | &#10003; (OOD) | &#10003; (OOD) |
| DPA4 | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| &#8627; DPA4-Air | &#10003; (OOD) | &#10003; (training) | not evaluated | not evaluated |
| GRACE | &#10003; (OOD) | &#10003; (pretraining) | &#10003; (OOD) | &#10003; (OOD) |
| &#8627; GRACE-1L | &#10003; (OOD) | &#10003; (pretraining) | not evaluated | not evaluated |
| &#8627; GRACE-2L | &#10003; (OOD) | &#10003; (pretraining) | not evaluated | not evaluated |
| &#8627; GRACE-2L-large | &#10003; (OOD) | &#10003; (pretraining) | not evaluated | not evaluated |
| eqV2 | &#10003; (OOD) | &#10003; (pretraining) | &#10003; (OOD) | &#10003; (OOD)&para;&para;&para; |
| eSEN | &#10003; (OOD) | &#10003; (pretraining) | &#10003; (OOD) | &#10003; (OOD) |
| NequIP-OAM-S | &#10003; (OOD) | &#10003; (pretraining)&#8214;&#8214; | &#10003; (OOD) | &#10003; (OOD) |
| NequIP-OAM-M | &#10003; (OOD) | &#10003; (pretraining)&#8214;&#8214; | &#10003; (OOD) | &#10003; (OOD) |
| NequIP-OAM-L | &#10003; (OOD) | &#10003; (pretraining)&#8214;&#8214; | &#10003; (OOD) | &#10003; (OOD) |
| PET-OMat-XS | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| PET-OMat-S | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| DPA-4.1C-Air | &#10003; (OOD) | &#10003; (training) | &#10003; (OOD) | &#10003; (OOD) |
| MACE-MH-1 | &#10003; (OOD)&sect;&sect;&sect; | &#10003; (training)&sect;&sect;&sect; | &#10003; (OOD) | &#10003; (OOD) |

\* Pre-trained on MACE-OMAT-0, fine-tuned on MatPES-PBE.

&para;&para; MACE-OMAT-0 is trained on OMat24, so OMat24 rattled-1000 is inside its training data.

&#8214;&#8214; NequIP-OAM-S, -M and -L use OMat24 for pretraining only and are then fine-tuned on sAlex + MPTrj.

&para;&para;&para; eqV2 predicts forces from a separate output head rather than as the energy gradient; its Ion Migration (NEB) entry carries a note on how this affects the full FP-NEB.

&sect;&sect;&sect; MACE-MH-1's `omat_pbe` head is trained on an OMat24 replay set, so OMat24 rattled-1000 is inside its training data. MatPES-PBE is not, although its shared backbone was also fine-tuned on MatPES-r2SCAN structures through a separate head.

The last two columns reflect what is currently published on the component leaderboards,
which now extends beyond the roster evaluated in the manuscript. eqV2 and eSEN are evaluated
for phase stability / ordering and ion-migration NEB.

The three r2SCAN-trained FPs are evaluated on MatPES-r2SCAN (training), in addition to the
models above.

---

## Contribute

Interested in evaluating a new foundation potential, or having it considered for inclusion in
FP-DeErr? See [Adding a Potential](ADDING_A_POTENTIAL.md) to integrate and evaluate a new model
with FP-DeErr; requirements are specified per component in the corresponding `requirements.txt`.
For inclusion in the public leaderboard, please contact Prof. Yifei Mo at <yfmo@umd.edu> with the
model name, version/checkpoint, and a link to the official implementation or model weights.

---

## Citation

If you use FP-DeErr, please cite the paper:

Kiyan Amirian, Ramanuja Srinivasan Saravanan, Felix Adams, Charles E Schwarz and Yifei Mo,
"FP-DeErr: Application-Oriented Error Decomposition for Foundation Potentials",
arXiv:2609.05714 (2026). <https://arxiv.org/abs/2609.05714>

```bibtex
@misc{amirian2026fpdeerr,
  author        = {Kiyan Amirian and Ramanuja Srinivasan Saravanan and Felix Adams and Charles E Schwarz and Yifei Mo},
  title         = {FP-DeErr: Application-Oriented Error Decomposition for Foundation Potentials},
  year          = {2026},
  eprint        = {2609.05714},
  archivePrefix = {arXiv},
  primaryClass  = {cond-mat.mtrl-sci},
  url           = {https://arxiv.org/abs/2609.05714}
}
```

---

## License

MIT. See [LICENSE](LICENSE).
