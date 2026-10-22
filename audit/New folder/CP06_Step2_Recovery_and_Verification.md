# CP06 Step 2 — Controlled voltage-continuation recovery

**Status:** add-on implementation with 16 synthetic/regression tests passing; **not** a completed TCAD physics run.  
**Basis:** the maintainer's CP06-1 report, stating 18 accepted 0–16.25 V points on the 0.2-µm grid at VGS = -20 V, with a reported 5.461 → 2.973 eV *minimax electrostatic barrier proxy*. The actual GitHub run files were unavailable for independent inspection in this environment.  
**Scope:** electron-only coupled Poisson / Scharfetter–Gummel continuation; no avalanche or hole transport.  
**Working assumption:** the checked-out JFET_TCAD branch is the Step 1–corrected branch and the `runs/CP06_020` directory contains `CP06_summary.json`, all accepted-point `*_fields.npz`, and their logs.

## 1. Decision and scientific interpretation

**CP06-1 outcome = BLOCKED, not failed physics.** The reported 2.488 eV fall (45.6% of the 5.461 eV reference) is evidence that the *electrostatic path-barrier proxy* changes with drain bias. It does **not** by itself demonstrate resolved source–drain punch-through. For CP06, measure the terminal current, current-resolution gate, local flux continuity, and the field / current path at high VDS. In particular, 2.973 eV remains about 115 times kT at 300 K, so do not claim thermionic channel opening merely from this barrier curve.

**Model-mode warning:** both the original CP06 runner and the v2 add-on explicitly call `create_jfet_device(..., mode="equipotential_gate")`. The separately fixed `bipolar_full` Gaussian P+ implant path is **not** active in this CP06-1 calculation. Also, an exponential carrier-density ceiling is not a full Fermi–Dirac transport model. These distinctions remain important to physical comparison with the paper.

The original runner only bisects **failed requested steps**. Setting `--max-refinements 100` alone does **not** force 0.5-V increments. The v2 add-on explicitly caps planned increments in the sensitive interval and retains failure-triggered bisection. It does not relax any physics or numerical tolerance.

## 2. Files and installation

Put `step2_dibl_continuation_v2.py` in the JFET_TCAD **repository root**. Put both `test_cp06_v2_regression.py` and `test_cp06_v2_schedule.py` inside `tests/` (they are portable; their import path is adjusted as necessary for that folder). **Do not replace the original `step2_dibl_continuation.py`.** Keep the existing `runs/CP06_020` directory read-only for the restart lineage.

From PowerShell, with the working folder in the JFET_TCAD repository (quote the drive path because it has spaces):

```powershell
Set-Location 'E:\MATERIAL\SOLI STATE\JFET\TCAD'
& .\.venv\Scripts\python.exe -m pytest -q tests/test_cp06_v2_regression.py tests/test_cp06_v2_schedule.py
```

The tests are synthetic numerical/planning tests, not an end-to-end TCAD validation. Their passing only certifies the v2 scheduler/loader logic in the tested environment.

## 3. Exact coarse-grid recovery command

First ensure `runs/CP06_020/CP06_summary.json` and the last accepted `CP06_VDS_16p25V_fields.npz` exist. Do not edit or overwrite them.

```powershell
& .\.venv\Scripts\python.exe .\step2_dibl_continuation_v2.py `
  --mesh 0.2 --gate -20 --pillar 2.2 --gap 1.8 --gate-depth 0.6 `
  --biases 0,1,5,20,50,100,200 `
  --dense-zone 5:30:0.5 --outer-max-step 5 `
  --min-step 0.125 --max-refinements 100 `
  --resume-from runs/CP06_020 `
  --save-fields all `
  --output runs/CP06_020_recovery_v2
```

How restart works:

1. Verify source SHA-256 for the six underlying solver modules; compare mesh, pillar, gate, gap, depth, tolerance and current floor.
2. Read every previously accepted point and corresponding NPZ; check exact active/gate masks and coordinate arrays, finite potentials and prior-stage validation metrics.
3. Recompute the **last 16.25 V** state with the live continuity and Poisson solvers before using it as a warm start. A mismatch blocks restart.
4. Skip proposed targets up to the last accepted bias; the default fine-zone schedule should next attempt 16.5 V, then 17.0 V, etc. Preserve previous accepted results, and record the old run's summary hash in the new output. **Historical points before 16.25 V are reused, not retroactively rerun at 0.5-V increments**; use a fresh sweep for a strictly uniform early-voltage schedule.
5. Report `COMPLETE` only when the requested upper target is accepted. All stages still need the same independent Poisson and current consistency gates.

**If the restart is rejected:** do **not** disable the source/geometry checks or copy only `psi` without quasi-Fermi state. Recheck whether the source has changed since CP06-1. If so, make a clean new run with no `--resume-from`, using a different output directory.

## 4. Fresh coarse and fine runs

For a fresh diagnostic on the same model:

```powershell
& .\.venv\Scripts\python.exe .\step2_dibl_continuation_v2.py `
  --mesh 0.2 --max-refinements 100 --min-step 0.125 `
  --dense-zone 5:30:0.5 --outer-max-step 5 `
  --output runs/CP06_020_fresh_v2
```

**Only after the coarse result has been evaluated**, run the 0.1-µm grid:

```powershell
& .\.venv\Scripts\python.exe .\step2_dibl_continuation_v2.py `
  --mesh 0.1 --max-refinements 100 --min-step 0.125 `
  --dense-zone 5:30:0.5 --outer-max-step 5 `
  --output runs/CP06_010_fresh_v2
```

The fine-grid run uses the **same physical device** with the same realized gate depth and gap. Passing CP05 geometry invariance is *not* proof of mesh-independent current, saddle barrier, or peak E field. A fixed-geometry three-grid study is still required for IMP-14.

## 5. Acceptance checkpoints

| Checkpoint | Evidence | Acceptance condition / disposition |
|---|---|---|
| CP06-A Provenance | JSON hashes; Git commit; source-tree status | Solver SHA, geometry and parameters match when resuming; otherwise STOP |
| CP06-B Continuation | attempts JSON, accepted-point CSV, histories | Reaches 200 V without accepting a failed step; failures and subdivisions retained |
| CP06-C Coupled solution | final Poisson residual and *undamped* correction | Each `<1.9e-6 V` (or documented fixed target), finite positive density; no fabricated values |
| CP06-D Current conservation | resolved source/drain currents and SG face fluxes | `abs(Is+Id)/max(abs(Is),abs(Id)) < 1e-5` **and** local normalized flux-divergence `<1e-5` when resolved |
| CP06-E Current resolution | `current_resolved`, floor, signed terminal currents | Current at target actually resolves above numerical floor; else **unresolved**, not punch-through |
| CP06-F DIBL trend | path-barrier curve, 2D current and field maps | Barrier-lowering trend, reproducible current increase and physically credible source–drain path |
| CP06-G Grid sensitivity | same-bias 0.2/0.1 µm maps and metrics | Differences documented; **no** grid independence claimed without IMP-14 |
| CP06-H Paper comparison | documented geometry, doping profiles, bias and normalization | **Pending** until 2.4-µm pillar / 0.5-µm implant and required physics are independently validated |

The previous checkpoint uses a **2.2 µm nominal pillar and 0.6 µm realized gate depth**. The paper's Figure 5 nominal design uses a **2.4 µm pillar and ~0.5 µm P+ implant** with Monte Carlo profiles. Therefore even reaching and resolving electron current at 200 V in CP06 does **not** automatically reproduce the published device or breakdown threshold.

## 6. Primary failure modes / mitigations

- **Further failure at 16.5 or 17.0 V:** record both the failed candidate and its last accepted predecessor; inspect the outer residual *and* undamped correction versus iteration, transport-conditioning warnings, quasi-Fermi potential, and density clipping. Only then try smaller `--min-step` or damping adjustments **in a separately named experiment**. Never define punch-through solely as solver nonconvergence.
- **Excessive runtime or memory:** one stage costs a coupled solve. The dense schedule creates many more stages than the former seven targets; run coarse first. Preserve all output and do not set a boundless refinement budget. Consider streaming checkpoint fields to disk in a subsequent engineering release; this patch still accumulates accepted fields in memory until final export.
- **Numerically unresolved current:** leave resolution explicitly false, even when raw arrays contain tiny nonzero floating-point values; current-conservation ratios based on roundoff are not physical.
- **Source SHA mismatch on restart:** do not bypass. Repeat from 0 V with the new source tree. Source provenance matters more than saving solver time.
- **Alternative numerical branches:** on a small voltage subset, repeat ascending / descending sweeps and compare states. Damping or small steps do not guarantee following the physically correct solution branch.
- **Over-interpreted barrier:** the implemented minimax value is an **electrostatic homogeneous-band proxy**, not a complete transport injection barrier referenced to all contact/band energetics. A lowering proxy does not establish carrier conduction.
- **High-field physics gap:** electron-only continuity has no impact ionization/hole multiplication. No result from this stage should be presented as the paper's -60 V avalanche breakdown.

## 7. Outputs to review

- `CP06_summary.json`: `continuation_status`, `requested_targets_covered`, `CP06_numerical_transport`, `last_accepted_bias_V`, solver provenance and `resume` lineage.
- `CP06_points.csv`: all solved stage residuals, current-resolution flags, signed `source_A_per_um` / `drain_A_per_um`, local continuity norm, barrier proxy, bottleneck location.
- `CP06_attempts.json`: the failed attempts that were bisected or stopped.
- `CP06_barrier_VDS.png` and `CP06_Id_VDS.png`: a trend *view*, not a pass/fail substitute.
- `CP06_VDS_*V_fields.npz`: actual SG electron-current face data and potential/quasi-Fermi arrays. Re-plot in common physical coordinates for fine/coarse comparison.

A v2 unit-test pass is separate from a full CP06 solver pass. No actual source modifications were pushed to GitHub and no live 0–200 V calculation was run here; the GitHub pages / repository checkout were not retrievable from this environment.
