# Additional MACE models

Audited leaderboard additions using the supplied references and unchanged public metric functions. Existing leaderboard rows are preserved.

These checkpoints target PBE/PBE+U material labels. MatPES-PBE supplies PBE labels; functional differences can affect errors. No r2SCAN rows are added. Exact training-set overlap is not audited; these are not claims of unseen-data performance.

## Exact checkpoints

- [MACE-OMAT-0 Small](https://github.com/ACEsuit/mace-foundations/releases/download/mace_omat_0/mace-omat-0-small.model): `mace-omat-0-small.model`, head `omat_pbe`, SHA-256 `0abfde07862cf1e93b8b4d03cb702f29ce9c344ff2fc4de2ec0d7166d6c113a5`. OMat24 training data; exact structure-level overlap is not audited.

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
