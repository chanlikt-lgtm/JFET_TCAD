# Step 2 / CP06 — Voltage continuation and solved electron current

**Project:** 4H-SiC vertical trench JFET based on Monaghan et al. (2023), KEM 948, 69–75.  
**Deliverable:** standalone additive runner `step2_dibl_continuation.py`, tests, and documented checkpoint gates.  
**Status:** implementation + unit tests complete; **not executed against the updated live GitHub solver**. CP06 physical validation remains pending.

## A. Purpose and scientific boundaries

At `VGS = -20 V`, solve the actual coupled Poisson/electron continuity system at ascending drain biases `VDS = 0, 1, 5, 20, 50, 100, 200 V`. Preserve a state only after nonlinear validation; warm-start the next stage with previous electrostatic **and** electron quasi-Fermi potential. On failure subdivide the voltage interval rather than silently accepting a nonconverged result.

The **paper reports** DIBL source-to-drain conduction near 200 V for a *2.4 µm nominal pillar* with 4e15 cm^-3 drift doping and ~0.5 µm implant depth. The Step 1 checkpoint geometry specified here is **2.2 µm pillar, 1.8 µm gap, 0.6 µm realized gate region** and is **not the same device**. CP06 numerical diagnosis using that geometry cannot establish a quantitative paper reproduction. No holes, avalanche, SRH/Auger, explicit Monte Carlo gate distribution, or device-wide gate-current response are introduced here.

## B. Important preflight discrepancy

The `main` branch returned by public GitHub retrieval during this preparation still contains detectable Step 1 blockers:

- `src/device.py` uses undefined `gate_y1_um` in `bipolar_full`.
- `src/gummel.py` contains a `* 1.15` fabricated field diagnostic and a drain-dominated centerline potential barrier.
- `src/poisson.py` retains the `exp(30)` cap.
- The original CLI's exact `-20 V / 200 V` path substitutes a prescribed quasi-Fermi profile and preassigned unresolved current. **Do not run that CLI path for CP06.**

The add-on checks the first three source problems and aborts by default. Use the verified Step 1 branch/commit. `--force-unverified-foundation` runs exploratory diagnostics only and **disables CP06 PASS**. It does not fix the foundational defects. GitHub `main` may be out of sync with a separate local or unpublished branch; confirm the source SHA-256 hashes and Git HEAD when available.

## C. Install

Place the provided `step2_dibl_continuation.py` at the **repository root**, adjacent to `simulate_kem948_fig5.py`, and copy `tests/test_step2_continuation.py` under the repository tests folder.

PowerShell (Windows):

```powershell
cd path\to\JFET_TCAD
py -3.13 -m venv .venv
.\.venv\Scripts\python.exe -m pip install numpy scipy matplotlib pytest
.\.venv\Scripts\python.exe -m pytest -q tests/test_step2_continuation.py
```

Bash (macOS/Linux):

```bash
cd /path/to/JFET_TCAD
python3 -m venv .venv
.venv/bin/python -m pip install numpy scipy matplotlib pytest
.venv/bin/python -m pytest -q tests/test_step2_continuation.py
```

These dependencies are top-level only; pin a complete environment lockfile when publishing a certified run. Never run with `--output` pointing to an existing nonempty folder (the script refuses overwrites).

## D. Execute and checkpoints

**CP06-0 — source provenance and geometry**

```bash
python step2_dibl_continuation.py --mesh 0.2 --output runs/CP06_020
```

This is the full seven-point schedule. The script records SHA-256 hashes for the six solver source files and this CP06 runner, confirms mirror symmetry and exact realized gate gap and depth, and refuses known old Step 1 defects.

**CP06-1 — coarse exploratory diagnosis**

```bash
python step2_dibl_continuation.py \
  --mesh 0.2 --gate -20 --pillar 2.2 --gap 1.8 --gate-depth 0.6 \
  --biases 0,1,5,20,50,100,200 --output runs/CP06_020
```

*(Choose only one of the two commands above, or use a separate output folder.)* The first bias is equilibrium drain voltage with reverse gate bias; source=0. Each requested stage uses the full Gummel loop, then **re-solves the Scharfetter–Gummel electron continuity system at the final potential** to calculate `Is`, `Id`, `Jx`, `Jy`, and the electron quasi-Fermi potential. Poisson is independently re-evaluated on that final state to avoid accepting a stale/pre-update stopping norm.

**CP06-2 — fine-grid sensitivity (not a certified mesh study)**

```bash
python step2_dibl_continuation.py --mesh 0.1 --output runs/CP06_010
```

Compare terminal `|Id|`, source-referenced barrier, local continuity, and field maps at the same *realized* device geometry. **This is only two grids.** CP05 geometry invariance is not mesh independence. A fixed-geometry three-grid asymptotic study remains Phase C / IMP-14.

**CP06-3 — optional exploratory bypass**

```bash
python step2_dibl_continuation.py --mesh 0.2 \
  --force-unverified-foundation --output runs/CP06_exploratory_old_main
```

Only for preliminary debugging on old `main`; `CP06_numerical_transport` stays `NOT_ESTABLISHED` regardless of the current plot.

## E. Artifacts and interpretation

Generated files:

| Output | Purpose |
|---|---|
| `CP06_summary.json` | Completion and checkpoint status, warnings, input schedule, geometry, package versions and source SHA-256 hashes and Git HEAD when available |
| `CP06_points.csv` | Accepted bias points, solved `Is`, `Id`, terminal balance, local continuity, independent Poisson residual/correction, bottleneck and current resolution |
| `CP06_attempts.json` | Each attempted bias including failed attempts and adaptive subdivisions |
| `CP06_VDS_*V_fields.npz` | Final-potential, electron density, quasi-Fermi, `Jx/Jy`, `Ex/Ey`, mask and coordinates in explicit units |
| `CP06_VDS_*V_history.csv` | Gummel iteration history from the underlying solver |
| `CP06_Id_VDS.png` | Absolute drain-current bias sweep; no physical leakage is inferred below the resolution floor |
| `CP06_barrier_VDS.png` | Electrostatic 2D minimax conduction-band barrier proxy, **not** a calibrated thermionic injection barrier |

NPZ `Jx_A_per_cm2`, `Jy_A_per_cm2` are the **SG face-oriented currents stored on upstream cells**, not smooth cell-centered vector fields. Field visualization may interpolate them for display, but terminal integration and conservation must use the conservative edge representation. Current is normalized as A per µm out-of-plane depth; the paper's total-amperes curves are not directly comparable without its device-area factor.

`barrier_proxy_eV` is calculated from `Ec(y,x)-Ec(source)=-q[psi(x,y)-psi_source]` assuming homogeneous bands, then computing the **minimum-bottleneck path** in the active 2D grid. The source reference and physical model are explicitly recorded. This is a controlled DIBL **proxy**; a full self-consistent injection-saddle characterization also needs contact energetics, explicit doping and better carrier statistics.

## F. Go / no-go decision and risk register

| Check | Go criterion | No-go response |
|---|---|---|
| Foundation / CP01–05 | No known defects; immutable hashes; exact realized depth/gap; mirror symmetry | Stop, fix Step 1. Exploratory override never certifies CP06 |
| All voltage stages | Every planned bias reached with accepted converged solution (optional extra adaptive points documented) | Stop, preserve last accepted point, bisect interval; never publish an unconverged point as data |
| Final-state Poisson | Independently re-evaluated residual **and** undamped correction each `<1.9e-6 V` (configurable) | Reject stage even if original Gummel `converged=True` |
| Electron density | Finite positive active carrier density | Reject stage, inspect boundary/transport conditioning |
| Current conservation | If **resolved**, `abs(Is+Id)/max(abs(Is),abs(Id)) < 1e-5` **and** max locally normalized finite-volume residual `< 1e-5` | Reject stage, inspect boundary fluxes and transport indexing |
| Resolution | Current exceeds user floor (default `1e-12 A/µm`), floating-roundoff estimate, and `100*|Is+Id|` | Label **UNRESOLVED**; do not treat underflow as leakage or a DIBL event |
| Barrier trend | Positive decrease from 0 V to 200 V (same model/mesh/contact reference) | DIBL not established even if terminal current rises |
| Numerical CP06 | All stages complete, final current resolved, barrier decreases, no foundation override | Else `NOT_ESTABLISHED` |
| Paper reproduction | Correct paper geometry/implant profile, on-state transfer validation, fixed-geometry mesh study, current normalization and spatial current agreement | Always `PENDING_INDEPENDENT_VALIDATION` in this package |

### Risk controls

1. **Stale/cached GitHub source or wrong branch:** use source SHA-256 hashes and Git HEAD when available in every run and verify the commit ID in Git. Never claim changes were pushed unless authenticated push and remote commit verified.
2. **False pass from a hard-coded 200 V branch:** the add-on never calls `simulate_nominal_paper_bias`; it calls `run_gummel_loop` at *every* bias.
3. **Using stale density/residual from before the last Gummel step:** recompute transport and Poisson on final `psi`, calculate fresh `phi_n`, current and fields.
4. **Extreme off-state cancellation:** numerical resolution floor is intentionally conservative; an unresolved current is **not** a predicted zero leakage current.
5. **Large voltage jumps / nonlinear branch loss:** warm start both potentials; subdivide failed steps; record all rejected attempts; stop after bounded refinement.
6. **Out-of-scope avalanche:** no impact-ionization or hole equation is added. Do **not** claim gate–drain avalanche or 1800 V predictions.
7. **Paper vs checkpoint device confusion:** the default 2.2 µm / 0.6 µm checkpoint geometry differs from the paper's 2.4 µm / 0.5 µm nominal geometry. Do not compare numerical breakdown voltages quantitatively.
8. **Current map and units:** SG face fluxes are converted A/m² to A/cm² by `1e-4`; electric field uses V/cm, and `A/µm` terminal normalization includes an out-of-plane width of `1e-6 m`.
9. **CP05 vs IMP-14:** geometrically identical 0.1 and 0.2 µm grids do not demonstrate mesh independence; require at least three fixed-geometry meshes.

## G. Verification actually performed in this deliverable

- `python -m py_compile step2_dibl_continuation.py`: **PASS**.
- `pytest -q tests/test_step2_continuation.py`: **11 passed**, using manufactured 2D barrier paths, conservation/resolution cases, validated/invalid result gates, synthetic adaptive continuation and source blocker checks.
- Full coupled bias sweep on the user's corrected solver: **NOT RUN**. The publicly accessible GitHub main files contradict the reported Step 1 state, and the execution environment cannot clone the GitHub repository. No physically measured DIBL onset or new terminal-current numerical result is asserted.

## H. Precise next acceptance point

1. Check out the corrected Step 1 commit/branch and confirm the first command passes the foundation gate without override.
2. Inspect `runs/CP06_020/CP06_summary.json`: `continuation_status == COMPLETE` and `CP06_numerical_transport == PASS`, or capture the first blocked bias and residual.
3. Compare the 0.1 and 0.2 µm fixed-geometry sweeps and measure whether the 2D current path appears in the gate neck. Keep mesh-independence and paper-validation statuses pending.
4. Only then proceed to Phase C (IMP-14) and separately obtain realistic Monte Carlo implant profiles. The hole/avalanche solver is a later milestone, not a shortcut around CP06.
