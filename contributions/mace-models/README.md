# Additional MACE models

Audited leaderboard additions using the supplied references and unchanged public metric functions. Existing leaderboard rows are preserved.

These checkpoints target PBE/PBE+U material labels. MatPES-PBE supplies PBE labels; functional differences can affect errors. No r2SCAN rows are added. Exact training-set overlap is not audited; these are not claims of unseen-data performance.

## Exact checkpoints

- [MACE-OMAT-0 Small](https://github.com/ACEsuit/mace-foundations/releases/download/mace_omat_0/mace-omat-0-small.model): `mace-omat-0-small.model`, head `omat_pbe`, SHA-256 `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`. OMat24 training data; exact structure-level overlap is not audited.
- [MACE-OMAT-0 Medium](https://github.com/ACEsuit/mace-foundations/releases/download/mace_omat_0/mace-omat-0-medium.model): `mace-omat-0-medium.model`, head `default`, SHA-256 `d4b14be9afa294eebdbe31a0280b26a0fa29715771e978cbfd3ca24e0d90307a`. OMat24 training data; structure-level overlap is not audited.
- [MACE-MH-1 (omat_pbe)](https://github.com/ACEsuit/mace-foundations/releases/download/mace_mh_1/mace-mh-1.model): `mace-mh-1.model`, head `omat_pbe`, SHA-256 `a522eb7f59c7879963d41586528f4980baf33e086c94aa92e3eafdeccad3be47`. OMat pretraining and cross-domain fine-tuning including MatPES-related data. No unseen-data claim; exact structure-level overlap remains unaudited.

## Reproduction

Use the component registries described in `ADDING_A_POTENTIAL.md`, with these identities and the following ASE calculator setup (replace MODEL_PATH and MODEL_HEAD with the pinned values above):

```python
from mace.calculators import MACECalculator
calc = MACECalculator(model_paths=MODEL_PATH, head=MODEL_HEAD,
                      device="cpu", default_dtype="float64")
```

Evaluation used mace-torch 0.3.16, float64, a 6 Å cutoff and no dispersion correction. Fixed cells, convergence thresholds and public metric definitions were retained. CPU/GPU execution and exact dependency versions remain recorded by stage; the NEB ASE version differs from the upstream reference implementation and is explicitly retained in provenance. Non-converged paths remain counted.

Source, checksums, audit records, standardized results, and command adapters: [review repository](https://github.com/michael-wang0605/fp-deerr-mace-evaluation). The accompanying manifest identifies the source audit and every contributed file.

Force detail rows are computed with the unmodified upstream force functions from checksum-verified retained shards, after the same finite-angle filtering as the notebooks. Main summary strings and phase rows are copied from the audited notebook outputs. NEB rows are copied verbatim from the public exporter outputs.

MACE-OMAT-0 Medium full-relaxation execution counts: {'cpu': 5821, 'cuda': 876}. CPU and CUDA used float64 and identical ASE FIRE settings (fixed cells, fmax 0.01 eV/Angstrom, 10,000-step limit). Complete calibration trajectories matched step counts, and numerical differences passed the recorded tolerances. Per-device versions, calibration proofs and execution counts accompany the results.

MACE-MH-1 (omat_pbe) full-relaxation execution counts: {'cpu': 5082, 'cuda': 1615}. CPU and CUDA used float64 and identical ASE FIRE settings (fixed cells, fmax 0.01 eV/Angstrom, 10,000-step limit). Complete calibration trajectories matched step counts, and numerical differences passed the recorded tolerances. Per-device versions, calibration proofs and execution counts accompany the results.

For MH1 singleton CUDA memory failures, validated saved-tensor disk storage was used. Every tensor retained its dtype and returned to its original CUDA device for arithmetic; no CPU model evaluation or precision reduction was substituted. The model audit lists each affected structure index and storage statistics, and the numerical/control proofs are included.
