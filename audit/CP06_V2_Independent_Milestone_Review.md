# CP06 Step 2 V2 — independent milestone review and recovery plan

**Date:** 2026-10-22  
**Project:** `chanlikt-lgtm/JFET_TCAD`  
**Basis:** Maintainer's CP06_020_recovery_v2 diagnostic report and inspection of the locally available V2 runner and its synthetic tests. **The live GitHub CSV/JSON/NPZ data could not be retrieved independently; reported values are not an independent rerun.**

## Decision

**CP06-2: PARTIAL / CONDITIONAL NUMERICAL EVIDENCE.** The report describes a resolved current above 55 V, a steeply declining 2-D electrostatic path-barrier proxy, and excellent terminal balance through 66.25 V. This is progress beyond CP06-1 (16.25 V). Do **not** close CP06 numerical transport or claim reproduction of paper Fig. 5; the recovered run stops at 66.25 V, and a second partial run reportedly reaches 77.09 V, below the 200 V target.

## Reported observations (not replayed here)

| VDS (V) | Path barrier proxy (eV) | Drain current (A/um) | Resolution flag | Relative terminal imbalance |
|---:|---:|---:|---|---:|
| 0 | 5.461 | -2.22e-20 | Unresolved | 0.98 (meaningless in noise) |
| 10.6 | 3.580 | 1.11e-20 | Unresolved | 1.0 (meaningless in noise) |
| 30 | 1.680 | 8.34e-21 | Unresolved | 1.0 (meaningless in noise) |
| 50 | 0.676 | -1.66e-13 | Unresolved | 8.39e-8 (not proof of resolved current) |
| 55 | 0.454 | -4.52e-10 | Resolved | 3.69e-11 |
| 60 | 0.280 | -2.01e-7 | Resolved | 7.20e-14 |
| 65 | 0.229 | -3.28e-6 | Resolved | 6.98e-15 |
| 66.25 | 0.221 | -4.77e-6 | Resolved | 2.08e-14 |
| 77.09 (second run) | Not supplied | magnitude 2.62e-5 | Not independently inspected | Not supplied |

- The resolved current rises by approximately **1.06e4 (4.02 decades)** between 55 and 66.25 V. A "14-order" comparison with 1e-20 A/um is **not physical**, because the earlier values are expressly unresolved numerical noise.
- The *first resolved sampled point* is 55 V, not a determined device breakdown voltage. The numerical resolution threshold and bias sampling affect this classification.
- The V2 runner uses a default absolute current-resolution floor of **1e-12 A/um**, augmented by a roundoff and terminal-imbalance floor; this is a numerical diagnostic, not a leakage model or current-based breakdown criterion.
- The path quantity is the minimum-over-paths of the maximum positive `(psi_source - psi)` value, in eV for a single electron under a homogeneous band-edge approximation. It is a **minimax electrostatic barrier proxy**, not a full injection barrier. The location of the bottleneck and its response to VDS should be checked against current streamlines and band-edge profiles.
- `VDS = 0 V, VGS = -20 V` is a zero-drain-bias, negatively gate-biased reference; call it the **VDS=0 baseline**, not unqualified whole-device thermal equilibrium.

## Scope and physical validation blockers

1. **Different device:** The CP06 checkpoint models a nominal 2.2 um pillar, 1.8 um gap, 0.6 um gate depth, with `mode="equipotential_gate"`. Monaghan et al.'s Fig. 5 is based on a 2.4 um nominal pillar, about 0.5 um Monte Carlo P+ implant and ND = 4e15 cm^-3. A current transition around 55-77 V in the checkpoint geometry cannot be equated with the paper's approximately 200 V failure.
2. **Transport physics:** Electron-only Poisson and Scharfetter-Gummel transport omit holes, avalanche generation, the explicit graded P+ region, and significant TCAD parameters. An exponential density cap is not a Fermi-Dirac solution.
3. **Remaining numerical checks:** The report gives terminal imbalance but not every resolved stage's local conservative flux-divergence, cross-sectional current constancy, density-clipping activity, or tolerance sensitivity. The V2 acceptance logic does check local continuity once current is resolved, but raw stage files are needed to replay it.
4. **Convergence vs physics:** A small Poisson residual is evidence that a discrete equation was solved, not grid convergence or fidelity to the published device.

## Next controlled run: 77.09 to 100 V

Keep previous runs immutable. **Only use the `--resume-from` path below if it contains the 77.09 V accepted NPZ, all historical field NPZs, summary and matching source hashes.** Otherwise restart from the 66.25 V directory or from 0 V as documented by the runner.

From the repo root in **PowerShell**:

```powershell
python step2_dibl_continuation_v2.py `
  --mesh 0.2 --gate -20 --pillar 2.2 --gap 1.8 --gate-depth 0.6 `
  --biases 0,1,5,20,50,65,80,100 `
  --dense-zone 5:30:0.5 --dense-zone 65:100:0.25 `
  --outer-max-step 2 --min-step 0.0625 --max-refinements 200 `
  --max-outer 1500 --tol 1.9e-6 `
  --resume-from runs/CP06_020_to200 `
  --save-fields all `
  --output runs/CP06_077_to100
```

**Why 100 V before 200 V:** The difficult 77 V region should be characterized separately. Run larger-range continuation only after checking why an accepted predecessor is followed by rejected steps. Do not weaken convergence tolerances or bypass source/geometry hash checks simply to reach an endpoint.

## Checkpoints and decisions

| Checkpoint | Evidence required | Gate |
|---|---|---|
| CP06-A, source/restart | `CP06_summary.json` provenance, hash of solver modules, geometry/mesh and matching last-state recomputation | Stop on mismatch |
| CP06-B, continuation | `CP06_attempts.json`, accepted stages, failure details and correction history | All attempted stages recorded; failed stages never used as warm starts |
| CP06-C, coupled residual | Independent final Poisson residual and undamped correction; positive finite density | Both below documented tolerance, no hidden relaxations |
| CP06-D, conservation | Signed Is/Id and `local_continuity_relative` at every **resolved** point | Each < 1e-5; additionally inspect cross-section current constancy |
| CP06-E, resolution | Resolution flag and numerical floor, especially 50-60 V | Resolved current exceeds documented noise floor by comfortable margin |
| CP06-F, physical path | Potential, density, Jx/Jy and electric-field maps at 50, 55, 60, 65, 77+ V | Continuous source-to-drain path; no NaNs or misleading color saturation |
| CP06-G, sweep branch | Ascending and descending/overlapping restart sweep for select biases | No unexplained hysteresis or branch jumping |
| CP06-H, grid comparison | Coarse 0.2 and fine 0.1 um at matching bias and geometry | Quantify sensitivity; three fixed-geometry grids needed before mesh-independence claim |
| CP06-I, paper comparison | 2.4 um, 0.5 um implant, independent profiles and current-normalization dimensions | Not currently met |

## Immediate risk mitigations

- **If the run blocks again:** inspect the *first failed trial* and its predecessor in `CP06_attempts.json`, Poisson residual/undamped correction history, electron density floor, quasi-Fermi profile and solver conditioning. Treat nonconvergence as a numerical issue, not proof of breakdown.
- **If current becomes very large:** test stability under 10x tighter tolerance and local mesh refinement; verify cell and gate-face electric-field values separately. Do not compare a 2-D `A/um` current directly with the paper's total amperes without the device-area factor.
- **If the source changes:** begin from 0 V rather than bypassing hash checks. Record full Git SHA, working-tree dirty status, NumPy/SciPy versions and CLI options.
- **If performance deteriorates:** the runner retains all accepted arrays in RAM; use bounded segments, preserving archived fields and immutable output directories. Reduce output scope only in separate reproducibility experiments, not a run intended for verified restart.

## Independent verification limits

The earlier available V2 runner was inspected locally, and its two synthetic/regression test files passed (**16/16** in this environment). The report's claimed **33/33** live-repository tests and 66/77.09 V numerical files were not independently run or downloaded. Public GitHub HTML retrieved for the new paths was unavailable or stale. These test categories should not be conflated.

**Decision:** Proceed with bounded 77.09 -> 100 V diagnostic continuation and raw numerical replay. **CP06 is not closed** until 200 V is reached on the specified checkpoint model with resolved conserved transport, and its predictive comparison to the paper remains a further independent validation task.
