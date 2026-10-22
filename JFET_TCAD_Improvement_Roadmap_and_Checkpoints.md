# JFET_TCAD: Point-by-Point Improvement Roadmap and Checkpoints

**Repository:** https://github.com/chanlikt-lgtm/JFET_TCAD  
**Audit baseline:** public `main` branch reviewed 2026-10-22  
**Document type:** actionable remediation backlog and verification / release-gate specification  
**Current qualification:** numerical research prototype; **NOT** independently validated as a reproduction of Monaghan et al. (2023) high-voltage DIBL or avalanche results.

> **Important:** This is a **plan, not an implementation report**. All checkboxes below start unchecked. Paths and failure modes are based on the source-level audit; the code was not freshly executed in the audit environment. The prescribed tolerances are **proposed engineering criteria**, not proof of agreement with experiment or Sentaurus. Freeze and approve numerical tolerances **before** comparing results to the paper.

## 0. How to use this document

1. Create one GitHub issue or pull request (PR) for each `IMP-xx` item. Record **owner**, **PR**, **commit SHA**, **date**, and **status** in the issue.
2. Work in the order shown. Never claim a later checkpoint passes because an earlier script exited with status 0.
3. Save raw results, solver diagnostics, inputs, logs, plots, test outputs, versions, and the exact commit SHA. A picture alone is **not** checkpoint evidence.
4. Mark an item **PASS** only when every acceptance check is satisfied and evidence is linked. Otherwise use **FAIL**, **BLOCKED**, or **NOT RUN**. Never silently convert unavailable physical tests to PASS.
5. When a calculation is illustrative, name and watermark it `ILLUSTRATIVE / NOT SOLVED`. The words `calculated`, `validated`, `reproduced`, or `exact match` are reserved for appropriately verified output.
6. Separate **software quality**, **numerical verification**, and **physical validation**. They answer different questions.

**Issue template:** `ID | owner | problem | changes | tests | inputs | raw outputs | observed metrics | thresholds | decision | reviewer | commit SHA`.

**Checkpoint ID note:** `CP00`-`CP23` in this **new roadmap** are proposed remediation checkpoints. The current `JFET_Checkpoint_Validator.py` already has a different `CP00`-`CP07` naming scheme; do **not** equate the two without a documented mapping/migration. Prefer stable namespaced IDs such as `ROADMAP-CP00` in a new machine-readable implementation.

**Checkpoint status semantics**

| Status | Meaning | Release behavior |
|---|---|---|
| `PASS` | Required checks executed, evidence stored, thresholds met | May satisfy its own gate only |
| `FAIL` | A required check ran and did not meet acceptance criteria | Blocks dependent gates |
| `BLOCKED` | Prerequisite or capability missing | Blocks dependent gates |
| `NOT RUN` | No valid execution evidence | Blocks release gates requiring the check |
| `NOT APPLICABLE` | Intentionally out of scope, with signed justification | Allowed only when the release scope explicitly excludes the capability |

## 1. Severity and dependency map

| ID | Priority | Work item | Main files | Checkpoint |
|---|---|---|---|---|
| IMP-01 | P0 | Freeze baseline and provenance | `README.md`, `runs/`, `results/` | CP00 |
| IMP-02 | P0 | Eliminate misleading simulated-output claims | `src/solver.py`, `reproduce_all.py`, Mathematica builders | CP01 |
| IMP-03 | P0 | Fail-closed checkpoint validator | `JFET_Checkpoint_Validator.py`, `run_all.bat`, `run_all.ps1` | CP02 |
| IMP-04 | P0 | Replace placeholder high-bias current with honest unavailable state | `simulate_kem948_fig5.py`, `src/postprocess.py` | CP03 |
| IMP-05 | P1 | Reproducible environment and CI | new `pyproject.toml`, `.github/workflows/` | CP04 |
| IMP-06 | P1 | Tests and negative tests | `tests/`, CLI | CP05 |
| IMP-07 | P1 | Repair `bipolar_full` branch | `src/device.py` | CP06 |
| IMP-08 | P1 | Preserve geometry under mesh refinement | `src/device.py` | CP07 |
| IMP-09 | P1 | Model contacts, asymmetry and doping consistently | `src/device.py`, `src/constants.py` | CP08 |
| IMP-10 | P1 | Centralize units and calibrated materials | `src/constants.py`, all solver modules | CP09 |
| IMP-11 | P1 | Verify Scharfetter-Gummel flux and terminal current | `src/bernoulli.py`, `src/transport.py` | CP10 |
| IMP-12 | P1 | Complete coupled convergence diagnostics | `src/gummel.py`, `src/poisson.py`, `src/transport.py` | CP11 |
| IMP-13 | P1 | Replace field / barrier shortcuts | `src/gummel.py`, `simulate_kem948_fig5.py` | CP12 |
| IMP-14 | P1 | Three-grid and sensitivity convergence | geometry, solvers, validator | CP13 |
| IMP-15 | P1 | Add physical hole and recombination model | `src/poisson.py`, `src/transport.py`, `src/gummel.py` | CP14 |
| IMP-16 | P1 | Establish resolved high-voltage/DIBL sweeps | `src/solver.py`, CLI | CP15 |
| IMP-17 | P1 | Couple avalanche generation and actual breakdown detection | `src/avalanche.py`, transport, solver | CP16 |
| IMP-18 | P1 | Reproduce Figure 2.1 study design | `src/solver.py`, results | CP17 |
| IMP-19 | P1 | Reproduce Figure 3 I-V families | `src/solver.py`, results | CP18 |
| IMP-20 | P1 | Reproduce Figure 4 off-state I-V (not interpolated Vbr) | `src/solver.py`, results | CP19 |
| IMP-21 | P1 | Reproduce Figures 5 and 6 with solved currents | `reproduce_all.py`, results | CP20 |
| IMP-22 | P2 | Correct Mathematica physics and cross-solver claims | `build_full_native_mathematica_tcad.py`, `.wl`, `.nb` | CP21 |
| IMP-23 | P2 | Publication, licenses, portability and audit trail | `README.md`, `report/`, scripts | CP22 |
| IMP-24 | P2 | Independent clean-room reproduction and release decision | all | CP23 |

**Dependency chain:** `CP00 -> CP01/CP02/CP03 -> CP04/CP05 -> CP06/CP07/CP08/CP09 -> CP10/CP11/CP12 -> CP13 -> CP14 -> CP15/CP16 -> CP17/CP18/CP19/CP20 -> CP21/CP22 -> CP23`. Independent documentation fixes may proceed earlier; **scientific approval cannot**.

---

## PHASE A - Stop invalid scientific claims and establish truth in outputs

### IMP-01 / CP00 - Snapshot the exact starting point [P0]

**Why:** The repository includes generated figures and checkpoint JSON, but a reproducible correction needs fixed code, environment and input data.

**Steps**
- [ ] Create an audit branch; record `git rev-parse HEAD`, date, OS, Python, NumPy/SciPy/Matplotlib versions and hardware/CPU information.
- [ ] Create `validation/baseline/` with a manifest enumerating every trusted source artifact and its SHA-256 hash (especially reference figure data and numerical run outputs).
- [ ] Execute existing tests, self-test, coarse/fine cases and **strict** validator on an untouched checkout; record stdout, stderr, exit codes and wall time; **do not edit saved results**.
- [ ] Identify which plots are copied/digitized reference data, illustrative graphics, Poisson-only results or transport-solved results.
- [ ] Add `validation/KNOWN_LIMITATIONS.md` and a provenance table for every committed figure.

**Existing commands (record actual exit codes; they may fail):**

```bash
python -m unittest discover tests -v
python simulate_kem948_fig5.py --self-test
python simulate_kem948_fig5.py --mesh 0.2 --control --output runs/CP04_coarse
python simulate_kem948_fig5.py --mesh 0.1 --control --output runs/CP05_fine
python JFET_Checkpoint_Validator.py --root . \
  --coarse runs/CP04_coarse --fine runs/CP05_fine \
  --run-self-test --strict --json runs/audit_baseline.json
```

**CP00 acceptance**
- [ ] Source revision and package versions are recorded.
- [ ] Every baseline command has an immutable log and exit code.
- [ ] Every figure has a declared data origin, mode (`solved` / `illustrative` / `reference` / `unknown`), and figure-to-input link.
- [ ] All known unvalidated physical claims appear as `BLOCKED`, never `PASS`.

**Evidence:** `validation/baseline/manifest.json`, `environment.txt`, `commands.log`, `figure_provenance.csv`, and `audit_baseline.json`. **Do not reinterpret historical saved figures as fresh test results.**

### IMP-02 / CP01 - Remove interpolated and synthetic results from scientific claims [P0]

**Source problems:** `src/solver.py::simulate_breakdown_characteristics()` hard-codes the 200-to-1800 V transition via a power-law interpolation; `reproduce_all.py` prescribes Gaussian `j_dibl` and `j_aval` maps and clips the avalanche electric field; some Mathematica code embeds `EXACT MATCH` parity values.

**Steps**
- [ ] Change Figure 4 output to `illustrative_breakdown_trend` or disable its generation until computed sweep data exist.
- [ ] Move prescribed Gaussian map generators to `examples/illustrative/` or remove them from `reproduce_all.py` entirely.
- [ ] Remove `Calculated Vbr`, `reproduced`, `exact match`, or similar assertions from any product that only uses constants or reference-supplied numbers.
- [ ] Never clip or artificially scale physical fields before calculating a reported maximum. If plotting with a limited color scale, limit only the **display**, and disclose saturation.
- [ ] Add metadata on every export: `data_origin`, `physics_mode`, `numerically_solved`, `current_resolved`, `converged`, `validation_status`.
- [ ] Add a regression test that refuses a `reproduction`-classified output containing prescribed placeholder data or a figure without provenance.

**CP01 acceptance**
- [ ] No computed/validated figure obtains breakdown voltage from the interpolation formula.
- [ ] No solved-current map is based on the Gaussian `j_dibl` or `j_aval` placeholder arrays.
- [ ] Existing illustrative outputs remain available only with conspicuous `NOT SOLVED` labels.
- [ ] All Figure 4/5/6 scientific claim statuses remain `BLOCKED` until CP19/CP20 pass.

**Evidence:** code diff, automated output-provenance test, figure inventory, before/after sample labels.

### IMP-03 / CP02 - Make validation fail closed by default [P0]

**Source problem:** `JFET_Checkpoint_Validator.py` presently returns nonzero for blocked physical stages only with `--strict`. The normal runners do not enforce the stricter meaning of scientific completion.

**Steps**
- [ ] Define two explicit scopes: `--scope numerical` and `--scope scientific` (or equivalent). Never let one be confused with the other.
- [ ] Make `--scope scientific` reject `FAIL`, `BLOCKED`, `NOT RUN`, `NOT VALIDATED`, `NOT AVAILABLE` and `REVIEW` at any required gate; set a nonzero exit status.
- [ ] Default user-facing reproduction runners and CI release jobs to the **scientific** scope; reserve numerical-only checks for clearly named development jobs.
- [ ] Require raw files, solved-mode flags, current-resolved flags and convergence reports, not just existence of images or a JSON field.
- [ ] Update `run_all.bat` and `run_all.ps1` to propagate nonzero process exit codes. No unconditional success banner.
- [ ] Replace the hard-coded `equilibrium_flux_identity = "PASS"` in the CLI self-test with a computed equilibrium-flux measurement and threshold.
- [ ] Add mutation/negative tests: delete a needed artifact; set `current_resolved=false`; inject `NaN`; set `converged=false`; mark CP07 unavailable; verify scientific gate fails in each case.

**CP02 acceptance**
- [ ] Current code fails the scientific release gate even when its basic numerical gate passes.
- [ ] A missing file, unsolved breakdown, nonconverged case or placeholder current always causes release failure.
- [ ] Validator report includes check ID, observed value, threshold, status, evidence path and reason.
- [ ] Numerical-only command is explicitly labeled `NUMERICAL CHECKS ONLY`.

**Evidence:** CI job logs showing expected failures, JSON gate report, Windows exit-code tests.

### IMP-04 / CP03 - Never export a placeholder as physical current [P0]

**Source problem:** `simulate_kem948_fig5.py` branches on `Vgs=-20 V, Vds=200 V` to a Poisson-only approximation; it writes a drain-current value of `4.14e-20 A/um`, sets `current_resolved=false`, and exports zero current-density arrays.

**Steps**
- [ ] Preserve the Poisson-only case only as `electrostatic_approximation`; never return it as transport-solved.
- [ ] Represent unavailable terminal current as `null`/masked/omitted; add `reason: TRANSPORT_NOT_SOLVED` instead of inventing a finite value.
- [ ] Export `jx/jy` only if actually computed; otherwise mark them missing, not genuine zero-current solutions.
- [ ] Do not compare these values to the paper's current density or leakage floor.
- [ ] Keep the 200 V case blocked until it goes through the same coupled current solver as other cases (IMP-16).
- [ ] Add tests for serializing unavailable measurements, plotting unavailable data, and refusing validation.

**CP03 acceptance**
- [ ] Placeholder numeric current is absent from all scientific results.
- [ ] `current_resolved` cannot be true unless terminal flux has been computed from a converged transport solution.
- [ ] Figure captions and JSON fields clearly distinguish electrostatics-only results from current solutions.

**Evidence:** exported JSON schema, failed physical gate test, representative electrostatics-only output.

---

## PHASE B - Reproducible software and defect repair

### IMP-05 / CP04 - Build a clean, reproducible environment [P1]

**Steps**
- [ ] Add `pyproject.toml` with supported Python version and all runtime/test dependencies; identify optional Mathematica and reporting tools separately.
- [ ] Pin resolved dependency versions in an appropriate lock file or reproducible constraints file; record the platform used for numerical reference outputs.
- [ ] Add clean install instructions for Linux and Windows, including `python -m venv`, package install and smoke-test commands.
- [ ] Add `.github/workflows/ci.yml` running lint, type/static checks as appropriate, unit tests and small deterministic numerical checks.
- [ ] Store large output runs outside the source tree by default; retain only curated tiny fixtures in version control.
- [ ] Document CPU, thread, solver/library and precision differences so non-bitwise reproducibility is not mistaken for failure.

**CP04 acceptance**
- [ ] Fresh install from dependency files works on at least one documented supported platform.
- [ ] CI independently installs dependencies and runs tests with no undeclared local paths.
- [ ] Tests do not depend on previously generated `runs/` results.

**Evidence:** install log, lock/constraints file, green clean-install CI job.

### IMP-06 / CP05 - Expand verification tests and enforce input validity [P1]

**Steps**
- [ ] Replace self-reported `PASS` strings with measured assertions for equilibrium flux, current conservation, Poisson residual and symmetry.
- [ ] Add unit tests for edge Bernoulli function, units, boundary masks, zero-voltage equilibrium, zero doping, mesh spacing and all modes.
- [ ] Add negative CLI tests for `--mesh <= 0`, nonfinite inputs, invalid mode, nonphysical geometry and filesystem failure.
- [ ] Make `--baseline-compat` functional and tested or remove/deprecate it; reject unsupported combinations.
- [ ] Add an end-to-end low-voltage golden regression with documented numerical tolerances (not arbitrary exact floating-point comparisons).
- [ ] Require each test to record the physical invariant it asserts and whether it is a numerical or empirical comparison.

**CP05 acceptance**
- [ ] No test silently passes on hard-coded status text.
- [ ] Invalid physical inputs fail early with a useful diagnostic and nonzero exit code.
- [ ] Baseline low-bias test is reproducible from a clean workspace.
- [ ] CI fails when a physical invariant is intentionally perturbed.

**Evidence:** test output, coverage summary (coverage is secondary to meaningful invariants), negative-test log.

### IMP-07 / CP06 - Repair `bipolar_full` geometry runtime failure [P1]

**Source problem:** `src/device.py` uses undefined `gate_y1_um` when constructing the nominal bipolar P+ profile.

**Steps**
- [ ] Define the intended gate extent once (e.g. derived as `gate_y0_um + gate_depth_um`, after checking coordinate conventions), and use it consistently.
- [ ] Validate `gate_depth_um > 0`, positive profile widths and bounds within domain; handle mode names explicitly.
- [ ] Review unused profile-distance variables and the claim that a simple Gaussian represents Monte Carlo implantation; describe it as **analytic approximation** unless data support more.
- [ ] Decide whether `bipolar_full` models real P+/N material regions versus an excluded equipotential gate and test those semantics.
- [ ] Add tests constructing both modes on multiple mesh sizes, with finite dopant maps and expected P+/N spatial positions.

**CP06 acceptance**
- [ ] `create_jfet_device(..., mode="bipolar_full")` executes without `NameError`, empty masks or invalid concentrations.
- [ ] Junction location/depth and doping integrals match the declared input model within discretization tolerance.
- [ ] Model limits are documented; **running the constructor does not mean bipolar transport is complete**.

**Evidence:** geometry/doping plots, tests and numeric mask/profile summary.

### IMP-08 / CP07 - Make geometry invariant under meshing [P1]

**Source problem:** integer rounding collapses some intended pillar widths and changes realized gate gaps and implant depths across grids. One mesh row also represents each heavily doped contact region.

**Steps**
- [ ] Define input geometry in physical coordinates independently of the grid (`pillar_width`, `gate_gap`, depth, source/drain contact thickness, radii, substrate length).
- [ ] Adopt edge-conforming nonuniform Cartesian or suitable conformal meshing; do not quietly round a 2.3 um device into 2.2 um.
- [ ] Preserve the actual intended **1.8 um** gap (where required), implant depths and all contact thicknesses on every mesh.
- [ ] Record requested and realized dimensions, cell counts, smallest feature resolution, region areas and contact-face lengths in `geometry.json`.
- [ ] Provide a mesh-density study for **2.2, 2.3, 2.4 um** widths. Distinct geometries must remain distinct for all mesh levels.
- [ ] Include a finite corner radius or mesh-resolved implant profile where physical field singularities would otherwise spoil field-convergence claims.

**CP07 acceptance**
- [ ] Requested-vs-realized feature differences are below a **predeclared** geometric tolerance (starting proposal: <= 1% for relevant dimensions, and tighter where needed to resolve a 0.1 um trend).
- [ ] No two distinct study geometries collapse to an identical realized mesh geometry.
- [ ] Mesh refinement does not change physical area or gate/contact placement materially.

**Evidence:** `geometry.json` for each mesh, dimension-comparison CSV, overlay plots, boundary-resolution images.

### IMP-09 / CP08 - Align contact, junction, and asymmetric implant physics [P1]

**Steps**
- [ ] Separate geometry, doping, and electrical boundary conditions; explicitly tag P+ implant, N+ source, N+ drain, drift and insulating interfaces.
- [ ] Implement optional left/right P+ implant profiles and trench-corner geometry as independent parameters; retain symmetric geometry as a controlled test case.
- [ ] Replace globally imposed `Vgate - 2.8` shortcuts with a documented, physically consistent boundary model appropriate to chosen gate mode.
- [ ] Make contact thickness in um independent of `dx/dy`; specify ohmic or other contact behavior and corresponding carrier boundary conditions.
- [ ] Check net ionized charge for each region and interface, with units and signs verified.
- [ ] Run symmetric-limit, left/right swap, zero-bias contact and independently biased gate tests.

**CP08 acceptance**
- [ ] Same model parameters produce identical physics under left/right swap (after corresponding coordinate reflection).
- [ ] Asymmetric input produces the intended asymmetric geometry/doping, not forced mirror symmetry.
- [ ] Every electrical boundary has a documented equation and material interpretation.

**Evidence:** parameter file, geometry+doping exports, BC table, symmetry/asymmetry tests.

### IMP-10 / CP09 - Establish a verified unit and material-parameter registry [P1]

**Source problems:** `src/constants.py` contains an inconsistent built-in-potential comment/value; several physical conversions and current/field units are scattered through the solver and notebook.

**Steps**
- [ ] Choose internal units (strongly prefer SI for PDE assembly); isolate conversion at input/output boundaries.
- [ ] Define helpers for `um <-> m`, `cm^-3 <-> m^-3`, `V/um <-> MV/cm`, `A/m^2 <-> A/cm^2`, and current per device depth.
- [ ] Compute built-in junction potential from an appropriate documented statistics model instead of maintaining contradictory constants and a separate hard-coded offset.
- [ ] Record 4H-SiC material parameters by temperature, orientation and cited reference: permittivity, intrinsic carrier density/statistics, mobility, lifetime, and electron/hole ionization coefficients.
- [ ] Verify constants against dimensional analysis and at least one independent authoritative material source; distinguish adopted approximations from published calibrated values.
- [ ] Add synthetic-unit tests with hand-computed reference values (e.g. **1 V/um = 0.01 MV/cm**).

**CP09 acceptance**
- [ ] All physical inputs and outputs have explicit units and conversions tested in CI.
- [ ] Junction model uses one documented consistent contact/built-in-potential convention.
- [ ] A parameter manifest, with provenance and uncertainty flags, travels with every run.

**Evidence:** `docs/units.md`, `docs/material_models.md`, unit test output, parameter manifest.

---

## PHASE C - Numerical integrity of the electron-only base

### IMP-11 / CP10 - Verify Scharfetter-Gummel and terminal-flux calculations [P1]

**Steps**
- [ ] Test Bernoulli `B(x)` for small x, large positive/negative x, and identity `B(-x) = exp(x)*B(x)` where numerically representable.
- [ ] Check equilibrium edge current tends to zero for a compatible electrochemical potential, over a range of meshes/dopings.
- [ ] Verify edge orientation/sign and the electron current equation on a uniform 1D analytic case.
- [ ] Calculate terminal currents from actual **boundary-face fluxes** rather than arbitrary interior-row samples; document 2D A/um normalization.
- [ ] Check each interior finite-volume node's continuity residual and global source+drain+gate balance (including generation/recombination once introduced).
- [ ] Check any edge-to-cell current-density visualization does not change a terminal-current measurement.

**CP10 acceptance**
- [ ] Equilibrium-flux error is below a physical-scale-aware threshold set before execution.
- [ ] Terminal conservation relative error meets a proposed **<= 1e-5** for resolved low-bias current; use an absolute error criterion when currents are near zero.
- [ ] Residuals and contacts are consistent for multiple mesh sizes and voltage polarities.

**Evidence:** analytic 1D comparison, flux-edge CSV, node residual norms, terminal current balance report.

### IMP-12 / CP11 - Validate the complete coupled residual, not a partial intermediate [P1]

**Source problem:** `src/gummel.py` tests a Poisson step/correction but does not verify the final fully coupled state after electron quasi-Fermi update. Nonconverged cases may still be exported as if successful.

**Steps**
- [ ] After the **final** Gummel update, recompute Poisson and electron-continuity residuals for the same fields; later include hole residual too.
- [ ] Use scaled absolute+relative norms on active nodes and boundary faces, with documented tolerances appropriate for each equation.
- [ ] Test positivity/finiteness of carrier concentrations and physical bounds of fields/occupancies where meaningful.
- [ ] Require terminal balance, maximum correction, residual criteria and numerical linear-solver success concurrently.
- [ ] Implement explicit statuses: `CONVERGED`, `MAX_ITERS`, `DIVERGED`, `UNPHYSICAL`, `LINEAR_SOLVER_FAILURE`, `NOT_SOLVED`.
- [ ] Use continuation/damped steps for difficult bias points; save full residual histories, accepted steps and rejected steps.
- [ ] Make exported metrics, CLI exit and validator depend on the final coupled status.

**CP11 acceptance**
- [ ] A perturbation of the final electron density or potential causes convergence verification to fail.
- [ ] Nonconverged sweeps do not appear as valid I-V data or generate release-qualified figures.
- [ ] Residuals printed in logs exactly match those calculated from the exported final state.

**Evidence:** residual-history files, tests including induced failure, solver status JSON.

### IMP-13 / CP12 - Fix electric-field and barrier observables [P1]

**Source problems:** `src/gummel.py` forces `max_gate_face_E` to at least `1.15 * max_cell_E` and defines a centerline barrier from a source-to-global-maximum potential difference. In high drain bias, that metric can simply track the drain voltage.

**Steps**
- [ ] Calculate E components on the appropriate physical mesh faces (and make their coordinate/units explicit).
- [ ] Remove the 15% multiplier; report actual calculated gate-interface face field and cell field as separate metrics.
- [ ] Define a conduction-band energy profile consistently with electrostatic potential, electron affinity, material offsets and quasi-Fermi levels.
- [ ] Extract a **source-to-channel** injection barrier/saddle along documented path(s); exclude the trivially high drain-contact value from the barrier definition.
- [ ] Report both the position and value of the saddle point and compare its change with Vds at fixed Vgs.
- [ ] Ensure field smoothing, display clipping or interpolated contours cannot modify stored physical metrics.

**CP12 acceptance**
- [ ] Reported gate field is traceable to field values on real interface faces, not a heuristic multiplier.
- [ ] A reference case demonstrates barrier extraction is not automatically equal to Vds.
- [ ] All field and barrier quantities are recomputable from raw exported fields and geometry.

**Evidence:** reproducible extraction script, raw E arrays, saddle-point/path CSV, analytical field/unit test.

### IMP-14 / CP13 - Demonstrate at least three-grid convergence [P1]

**Source problem:** current CP05 compares only 0.2 and 0.1 um grids. Previously committed coarse-to-fine differences include approximately 8.7% in low-bias current and 17.8% in a nominal high-bias maximum field; they are warnings, **not** a convergence certification.

**Steps**
- [ ] Use **three or more geometry-consistent meshes** (example target spacings 0.2, 0.1, 0.05 um if feasible; adapt to physical features and available memory).
- [ ] Keep doping dose, contact dimensions, trench radius, all terminal bias and constitutive model **identical** on each mesh.
- [ ] Compare terminal I, Vth, channel barrier, global/interface field, integrated charges and ionization generation where available.
- [ ] Calculate relative changes and, where mathematically justified, observed order and a Richardson/GCI-type error estimate. Do not apply smooth-field extrapolation blindly to singular corner peaks.
- [ ] Refine locally at gate corners/junctions and check convergence of **physical rounded-corner field**, not mesh-artifact singularities.
- [ ] Repeat an additional convergence study at a different gate bias or relevant operating mode.

**CP13 acceptance**
- [ ] All compared meshes represent the same geometry.
- [ ] Proposed starting target: finest two meshes differ by <= 5% in key integral quantities, with tighter 1-2% targeted for final paper comparisons. Thresholds must be justified and frozen in advance.
- [ ] Field peaks and breakdown-related quantities pass a separately justified spatial-error analysis; if they do not, CP13 remains `BLOCKED`.
- [ ] The result is a convergence **trend and estimated uncertainty**, not just two percentages.

**Evidence:** mesh inventory, convergence table, rate/error plots, raw numerical metrics, signed decision.

---

## PHASE D - Implement missing semiconductor physics and high-voltage solving

### IMP-15 / CP14 - Implement a physically coupled two-carrier baseline [P1]

**Why:** Electron-only Poisson/continuity cannot describe gate-injected holes, electron-hole pair multiplication or coupled avalanche breakdown.

**Steps**
- [ ] Extend the unknowns to potential, electron density/quasi-Fermi potential and hole density/quasi-Fermi potential.
- [ ] Couple Poisson charge to `p - n + N_D^+ - N_A^-` with appropriate statistics and ionization assumptions.
- [ ] Implement hole Scharfetter-Gummel flux and **both** continuity equations with consistent signs, boundary conditions and dimensional units.
- [ ] Add documented recombination (at least a defensible baseline such as SRH), mobility and carrier statistics; distinguish mandatory calibrated models from optional upgrades.
- [ ] Implement gate P+/N junction physics and electron/hole contacts. Revisit whether depletion approximation or Fermi-Dirac statistics are required at degenerate P+/N+ regions.
- [ ] Verify on 1D equilibrium P-N junction and a simple forward/reverse bias diode before using the full JFET geometry.
- [ ] Add conservation test: net electron-hole pair generation must contribute consistently to both continuity equations.

**CP14 acceptance**
- [ ] Self-consistent electron+hole solution converges in basic verification structures.
- [ ] Equilibrium currents and charge-neutrality limits are appropriate; terminal current and continuity residuals pass declared tolerances.
- [ ] Gate current can be computed from transport rather than imposed or omitted.
- [ ] Materials and physical assumptions are declared with calibration references.

**Evidence:** equations/specification, diode benchmarks, electron/hole flux maps, solver residuals.

### IMP-16 / CP15 - Resolve high-voltage off-state transport and DIBL [P1]

**Steps**
- [ ] Remove the special high-bias Poisson-only bypass for production/scientific runs.
- [ ] Solve the coupled device at Vgs=-20 V over an adaptive Vds ramp from a converged equilibrium/low-voltage state through the relevant ~200 V region.
- [ ] Add robust continuation and smaller steps near sharp current onset, recording any failed continuation step rather than silently using a fallback value.
- [ ] Define an off-state current threshold or slope/bifurcation extraction criterion **before seeing** the sweep output; separate a defined threshold from physical mechanism identification.
- [ ] Compute conduction-band barriers/path connectivity versus Vds, and identify current path from solved electron/hole fluxes.
- [ ] Verify that the high-bias current is resolved above the documented solver accuracy and that the source/drain/gate current balance holds.
- [ ] Show that the onset correlates with a falling source-channel barrier and is not merely an electric-field contour or a fabricated Gaussian.

**CP15 acceptance**
- [ ] Full solved off-state `Id-Vds` data exist with final convergence residuals and resolved terminal currents at each accepted point.
- [ ] DIBL barrier lowering is numerically measured on the same device as Vds changes.
- [ ] Breakdown/onset label is not assigned at 200 V by fiat; the actual extracted value and uncertainty are reported even if they differ from the paper.
- [ ] Sensitivity to voltage-step size and mesh is documented.

**Evidence:** raw bias sweep CSV, E_C cutlines and saddle map, current-path data, solver logs.

### IMP-17 / CP16 - Integrate impact ionization and extract avalanche onset [P1]

**Source problem:** `src/avalanche.py` is a diagnostic formula, not a self-consistent generation term. It assumes `dy_cm = 0.1e-4` regardless of mesh and lacks solved hole-current input.

**Steps**
- [ ] Choose and cite calibrated 4H-SiC electron and hole ionization coefficients, their formula, temperature behavior, crystallographic direction and validity range.
- [ ] Resolve the mismatch between documented `alpha = a * E * exp(-b/E)` and the actually implemented `a * exp(-b/E)`; choose the dimensionally correct form for the parameter units in use.
- [ ] Calculate `G_ii = (alpha_n |Jn| + alpha_p |Jp|)/q` from solved carrier fluxes and local field (with the precise local model documented).
- [ ] Add `G_ii` as a coupled **source** in both carrier continuity equations; implement numerically stable continuation and convergence reporting.
- [ ] For any diagnostic ionization integral, use actual face lengths / field line trajectories; do **not** use fixed 0.1 um spacing or column sums as a mesh-independent avalanche criterion.
- [ ] Run Vgs=-60 V drain-bias sweeps through the actual rising-current region without artificially clipping E values or forcing onset near 1800 V.
- [ ] Perform model sensitivity to mobility, lifetime, ionization coefficients, temperature and trench-corner radius.
- [ ] Verify total pair-generation rate and collected current satisfy continuity and charge balance.

**CP16 acceptance**
- [ ] A zero-ionization-coefficient control suppresses avalanche generation and its associated multiplication.
- [ ] The full coupled solver yields nonzero **solved** hole current and positive physically meaningful generation where avalanche occurs.
- [ ] Extracted avalanche onset is stable to further mesh/voltage-step refinement within approved uncertainty bounds.
- [ ] There is no hard-coded 1800 V onset, synthetic current map or clipped physical E used in the breakdown decision.

**Evidence:** alpha-model citation/test, G_ii field export, electron/hole currents, I-V sweep, coefficient and mesh sensitivity report.

---

## PHASE E - Reproduce the actual paper experiments

**General rule for this phase:** Reproduction means **independent solved data using stated physical parameters and an agreed extraction method**. Agreement with one reference number is not sufficient; compare trend, geometry, units, biases, shape, uncertainty, and mechanism. Digitized paper curves may be used as **reference datasets** only, with their provenance recorded.

### IMP-18 / CP17 - Figure 2.1: Vth vs pillar width and doping [P1]

**Steps**
- [ ] Extract the paper's exact sweep matrix: widths, drift-doping levels, Vds bias, implantation profile and stated Vth extraction definition.
- [ ] Run every width/doping point with the **realized geometry** verified by CP07.
- [ ] Extract Vth from solved current-transconductance data. Implement the stated transconductance-change method correctly; do not silently substitute `argmax(gm)` if the paper specifies another condition.
- [ ] Report sampling resolution, interpolation/derivative method, uncertainty and sign convention.
- [ ] Compare numerical curves with digitized paper values in a plot and machine-readable table; report deviations honestly.

**CP17 acceptance**
- [ ] No Vth is entered as a fixed table entry or copied paper value.
- [ ] The complete width/doping matrix is reproduced or any missing point remains `BLOCKED`.
- [ ] Extraction-method and mesh sensitivity tests pass; deviations have a clear error analysis.

**Evidence:** `validation/paper/figure_2_1/` with reference CSV, solved CSV, scripts, comparison and metrics.

### IMP-19 / CP18 - Figure 3: on-state I-V families [P1]

**Steps**
- [ ] Match the paper's 2.2 and 2.4 um geometries, doping, Vgs values and Vds=0..10 V sweep.
- [ ] Use the converged coupled (or explicitly approved valid low-bias) transport solver; export all terminal currents.
- [ ] Extract the width-dependent current reduction **from calculated I**, not a hard-coded 33% assertion.
- [ ] Compare curves, slope, onset/saturation features and paper reference points with uncertainty bars/tables.
- [ ] Retest terminal current conservation and mesh convergence at representative high-current points.

**CP18 acceptance**
- [ ] Curves come from raw solved bias sweeps with no embedded reference-current table.
- [ ] Reported width effect equals the calculation `100*(1 - I_2.2 / I_2.4)` at matched bias, with units and signed comparison.
- [ ] Any mismatch to the cited ~33% paper trend is reported rather than tuned away without disclosure.

**Evidence:** `validation/paper/figure_3/`, solved bias CSVs, comparison plot and uncertainty report.

### IMP-20 / CP19 - Figure 4: true off-state Id-Vds curves and Vbr [P1]

**Steps**
- [ ] Run full off-state current sweeps for Vgs = -20, -30, -40, -50 and -60 V (or the exact gate-bias set in the paper).
- [ ] Use consistent geometry and physics model across the series; refine Vds near each detected onset.
- [ ] Predefine and document the Vbr criterion (absolute I, current slope, multiplication threshold, or other physically argued criterion); report sensitivity to criterion choice.
- [ ] Export `Id`, `Is`, `Ig`, hole and electron components, maximum E, G_ii, convergence and mechanism diagnostics at every point.
- [ ] Distinguish DIBL/punch-through from avalanche using current-path/barrier and generation evidence, not Vgs labels alone.
- [ ] Replace `simulate_breakdown_characteristics()` interpolation with an extractor consuming raw solved sweep output.

**CP19 acceptance**
- [ ] Figure 4 is an Id-Vds family from computed terminal currents; any Vbr-vs-Vgs summary is **derived** from those curves.
- [ ] No `200 + 1600*alpha**1.3` or other assumed Vbr formula is used in the science export.
- [ ] Every extracted point links to its criterion, bracketing biases, final residual and run manifest.

**Evidence:** `validation/paper/figure_4/`, I-V data, onset detection results, mechanism table.

### IMP-21 / CP20 - Figures 5 and 6: solved current and electric-field maps [P1]

**Steps**
- [ ] Match the **2.4 um** nominal paper geometry and its gate profiles; do not use the CLI's default 2.2 um device without clear qualification.
- [ ] For Fig. 5, use converged Vgs=-20 V high-bias solved current density, electric field and barrier data. Verify DIBL pathway without a prescribed Gaussian current density.
- [ ] For Fig. 6, use converged Vgs=-60 V solved impact-ionization-generated electron/hole currents and real field components; do not use `j_aval` or field clipping.
- [ ] Export raw x/y grid, masks, `psi`, `n`, `p`, `Jn`, `Jp`, `E`, `G_ii`, contact currents and full solver diagnostics.
- [ ] Plot log-current scales with explicit data floors and colorbar units; floors may affect display but **not** physical integration or onset extraction.
- [ ] Compare pathway location, spatial structure and peak-field location against the paper, noting boundary-condition and geometry uncertainty.

**CP20 acceptance**
- [ ] Figures 5.1 and 6.1 use `Jn + Jp` or separately labeled solved components, never synthetic maps.
- [ ] Figures 5.2 and 6.2 use unmodified solved physical E for all numerical metrics.
- [ ] CP15 and CP16 are PASS and all Figure 5/6 fields are reconstructable from saved numeric arrays.

**Evidence:** `validation/paper/figures_5_6/`, raw field files, plotted comparisons, solver manifests.

---

## PHASE F - Independent comparison, documentation and release

### IMP-22 / CP21 - Repair Mathematica notebooks and remove unsupported parity [P2]

**Source problems:** notebook builders hard-code parity tables and current curves, use absolute Windows paths, model a geometry unlike the Python JFET, and convert a potential gradient in V/um to MV/cm using `10^-4` instead of `10^-2`.

**Steps**
- [ ] Decide and document whether Mathematica is **(a) independent PDE solver** or **(b) visualization/postprocessing**. Never imply independent validation when it only plots imported values.
- [ ] Fix V/um -> MV/cm conversion to multiply by `0.01`; verify with a linear-potential unit test.
- [ ] Use the same geometry, doping, contacts, mesh-resolved feature sizes and physical equations as Python where a cross-solver comparison is claimed.
- [ ] Remove hard-coded `EXACT MATCH` tables and reference-derived results from any calculated-parity section.
- [ ] Export solved numeric arrays and compare potential, current, E, contacts, mesh convergence and residuals at **identical** physical cases.
- [ ] Replace `E:\...` and `C:\Program Files\...` assumptions with configurable paths and dependency checks; ensure rerunning the notebook is possible on a supported host.
- [ ] Resolve any inconsistent percentage claims (for example, the displayed 4.90e-5 to 3.95e-5 A/um difference is ~19.4%, not 33%).

**CP21 acceptance**
- [ ] Every cross-solver parity entry is computed by a script from two independently generated numeric result files.
- [ ] Units, boundary conditions, geometry and solver capabilities are equivalent for the compared cases.
- [ ] Notebook execution logs and versions are saved; unsupported comparisons are labelled `NOT COMPARABLE`.

**Evidence:** executable notebook/script, exported arrays, parity-comparison script and residual table.

### IMP-23 / CP22 - Fix README, report, portability, security and licensing [P2]

**Steps**
- [ ] Replace the README's "complete reproduction" assertions with explicit levels: demo, numerical check, device-model validation, paper reproduction.
- [ ] Update `report/jfet_tcad_report.tex` and generated PDF only **after** all reported values trace to solved runs; mark incomplete physics as limitations.
- [ ] Add `docs/physics_assumptions.md`, `docs/verification_protocol.md`, `docs/limitations.md`, and a single source of truth for gate status.
- [ ] Document exact paper DOI (https://doi.org/10.4028/p-e6c13m), digitization methodology, measured/reference vs computed legend styles, and comparison tolerances.
- [ ] Remove hard-coded absolute paths, handle cross-platform file names and ensure scripts honor output directories and failure codes.
- [ ] Add an appropriate `LICENSE` only after confirming ownership/right to license original code; separately identify third-party data and paper-image rights.
- [ ] Run dependency vulnerability, secret and license scans; remediate findings and save reports. Do not label project secure merely because no obvious exploit appeared in static review.
- [ ] Establish contribution requirements: review from numerical-methods and device-physics reviewers for changes affecting accepted reference outputs.

**CP22 acceptance**
- [ ] README, report, figures, notebook and validation JSON state the **same** current scientific scope.
- [ ] All reported values can be traced to data origin, commit and parameter set.
- [ ] Installation and run documentation execute as written on the declared platforms.
- [ ] Security/licensing checks are documented, with any residual risks tracked.

**Evidence:** documentation diff, scan reports, install replay logs, rights/licensing inventory.

### IMP-24 / CP23 - Independent reproducibility review and final sign-off [P2]

**Steps**
- [ ] Freeze a release candidate commit, lockfile, physics parameters, device geometry, scripts and acceptance thresholds.
- [ ] Ask a reviewer who did **not** develop the models to reproduce all scientific claims in a clean environment without using previously generated result files.
- [ ] Run every numerical and physical checkpoint; capture failures and verify validators catch deliberately corrupted cases.
- [ ] Review uncertainties and mechanism attribution: geometry, material parameters, contact physics, mesh, voltage-step selection, statistical model and reference-data digitization.
- [ ] Compare against an **independent** TCAD implementation or experimental data where available. Paper-curve agreement alone, especially with tuned parameters, is not independent validation.
- [ ] Produce a release decision: `NUMERICAL_PROTOTYPE`, `DEVICE_MODEL_VALIDATED` or `PAPER_REPRODUCTION_QUALIFIED`; record explicitly which claims remain excluded.
- [ ] Sign the decision with owner, numerical reviewer and physics reviewer; archive a release bundle that can be replayed.

**CP23 acceptance**
- [ ] Required gates are all PASS for the chosen declared release level.
- [ ] Clean-room runs reproduce numerical metrics within approved uncertainty bounds and create all artifacts from source.
- [ ] No missing / illustrative / nonconverged result is represented as validation evidence.
- [ ] An explicit signed limitations statement accompanies the release.

**Evidence:** `validation/release/<tag>/` with manifest, logs, all metrics, independent review and signed qualification decision.

---

## 2. Release gates (mandatory policy)

| Gate | Scope | Required checkpoints | Status at audit | Rule |
|---|---|---|---|---|
| G0 - Truthful prototype | Accurate labels and no misleading physical claims | CP00-CP03 | **OPEN** | May release only as explicitly unvalidated prototype |
| G1 - Reproducible numerical core | Clean environment, reliable discrete equations, geometry, residuals and mesh study | CP04-CP13 | **OPEN** | May describe as numerically verified for tested range; **not** breakdown validated |
| G2 - Physically credible JFET | Two-carrier model and validated low-bias device observables | CP14, CP17, CP18 + G1 | **OPEN** | May describe as physically modeled within disclosed assumptions |
| G3 - Breakdown reproduction | Solved DIBL and avalanche, high-bias I-V, all paper maps | CP15, CP16, CP19, CP20 + G2 | **BLOCKED** | Required to claim Fig. 4/5/6 reproduction |
| G4 - External scientific release | Independent cross-check, documentation/provenance and sign-off | CP21-CP23 + G3 | **BLOCKED** | Required for publication-grade / engineering qualification claims |

**No false pass:** `PASS` on CP05 (tests), CP11 (solver convergence) or CP13 (mesh study) does **not** imply CP15/CP16 (DIBL/avalanche) have passed.

### Suggested machine-readable gate result (new schema, not currently implemented)

```json
{
  "checkpoint_id": "CP16",
  "scope": "scientific",
  "status": "BLOCKED",
  "reason": "coupled hole transport and impact-ionization validation not complete",
  "required": true,
  "code_commit": "<git SHA>",
  "inputs_sha256": "<hash>",
  "evidence": [],
  "criteria": [
    {"name": "hole_continuity_final_residual", "threshold": "approved limit", "observed": null},
    {"name": "avalanche_onset_grid_sensitivity", "threshold": "approved limit", "observed": null}
  ],
  "reviewer": null
}
```

## 3. Suggested GitHub PR sequence and merge rules

| PR | Depends on | Changes | Merge only if |
|---|---|---|---|
| PR-01 | none | IMP-01 to IMP-04 | CP00-CP03 evidence exists; scientific gate correctly fails on legacy code |
| PR-02 | PR-01 | IMP-05 to IMP-07 | CI works and device mode bug is covered |
| PR-03 | PR-02 | IMP-08 to IMP-10 | Geometry/BC/unit checks pass on clean installs |
| PR-04 | PR-03 | IMP-11 to IMP-13 | Numerical invariant tests pass; no fake fields/barriers |
| PR-05 | PR-04 | IMP-14 | Three-grid study accepted for supported observables |
| PR-06 | PR-05 | IMP-15 | Coupled two-carrier benchmark tests pass |
| PR-07 | PR-06 | IMP-16 and IMP-17 | Real high-voltage transport and avalanche checks pass |
| PR-08 | PR-07 | IMP-18 to IMP-21 | Paper figure comparisons generated from raw solved data |
| PR-09 | PR-08 | IMP-22 and IMP-23 | Cross-solver/documentation review complete |
| PR-10 | PR-09 | IMP-24 | Independent replay and release sign-off complete |

**PR definition of done:** code changes + focused tests + negative tests where meaningful + new numerical evidence + updated documentation + reviewer sign-off. Never merge solely because a plot visually resembles the paper.

## 4. Daily progress checklist (copy into every work session)

- [ ] Working branch and HEAD SHA captured.
- [ ] Current `IMP-xx` and dependency gates identified.
- [ ] Expected physical invariant and acceptance threshold written **before** code edits.
- [ ] Exact commands, parameter file and geometry recorded.
- [ ] Unit tests, focused physics test and a deliberate failure test executed.
- [ ] Logs, residual histories, metrics and raw arrays saved.
- [ ] Generated figures carry origin/mode/status and do not hide clipped/masked data.
- [ ] A reviewer can reproduce the evidence from a clean checkout.
- [ ] Checkpoint status and reason updated; next checkpoint not promoted prematurely.

## 5. Suggested evidence directory structure (new, not present in the baseline)

```text
validation/
  KNOWN_LIMITATIONS.md
  baseline/
    manifest.json
    environment.txt
    commands.log
    figure_provenance.csv
  reference/
    paper_2023/
      reference_manifest.json
      digitization_notes.md
      figure_2_1.csv
      figure_3.csv
      figure_4.csv
  checks/
    CP00/
    CP01/
    ...
    CP23/
  paper/
    figure_2_1/
    figure_3/
    figure_4/
    figures_5_6/
  release/
    <tag>/
      environment.txt
      inputs.json
      provenance.json
      numeric_metrics.json
      checkpoint_results.json
      decision.md
```

For each run, archive at minimum: `git_sha`, timestamp, executable version, physical parameters and their units, mesh geometry, gate/drain/source biases, solver mode, convergence flags, final residual norms, current balance, contact currents, exact input and output hashes, and measurement/extraction criteria. File hashes prevent mixing output from different code and parameter versions.

## 6. Recommended first working session

1. **Do CP00:** freeze HEAD SHA and rerun baseline commands above on a clean checkout. Expect the strict scientific validator to report blocked physical checks; do not edit the data to make it pass.
2. **Do CP01:** relabel or isolate interpolated Figure 4 breakdown and synthetic Figure 5/6 maps. Mark previous publication-grade claims unsupported.
3. **Do CP02:** enforce scientific gate failures and add negative tests; change Windows runners to propagate exits.
4. **Do CP03:** remove numeric placeholder current and add explicit `TRANSPORT_NOT_SOLVED` export semantics.
5. Open PR-01 with a **truthful state of the model**. Only then begin geometry, solver and physics upgrades.

## 7. Source links and audit basis

This plan is grounded in the publicly accessible repository source, especially:

- [Repository README](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/README.md) and [official runbook](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/JFET_Simulation_Setup_and_Execution_Guide.md)
- [`src/device.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/device.py) - geometry rounding, mirror symmetry, `bipolar_full` undefined variable
- [`src/solver.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/solver.py) - hard-coded breakdown-voltage interpolation, threshold extraction
- [`src/gummel.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/gummel.py) - convergence checks, field factor and barrier metric
- [`src/transport.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/transport.py) - electron-only transport and terminal current extraction
- [`src/poisson.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/poisson.py) - Poisson model
- [`src/avalanche.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/avalanche.py) - decoupled generation diagnostic and fixed mesh step
- [`src/constants.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/src/constants.py) - physical constants and built-in-potential inconsistency
- [`simulate_kem948_fig5.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/simulate_kem948_fig5.py) - high-bias electrostatic special branch and placeholder current
- [`reproduce_all.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/reproduce_all.py) - synthetic current maps and capped displayed field
- [`JFET_Checkpoint_Validator.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/JFET_Checkpoint_Validator.py) - strict vs default outcome, CP06 and CP07 blocked
- [`build_full_native_mathematica_tcad.py`](https://github.com/chanlikt-lgtm/JFET_TCAD/blob/main/build_full_native_mathematica_tcad.py) - hard-coded parity and Mathematica unit/geometry mismatch
- [Monaghan et al., Key Engineering Materials 948 (2023), DOI 10.4028/p-e6c13m](https://doi.org/10.4028/p-e6c13m) - target publication

**Audit limitation:** This document was produced from source inspection and prior committed checkpoint evidence, not fresh execution of the GitHub repository in this environment. Actual pass/fail outcomes, new accuracy thresholds and physical parity remain to be established during implementation.
