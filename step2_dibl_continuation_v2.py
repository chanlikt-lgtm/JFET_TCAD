#!/usr/bin/env python3
"""CP06 electron-only 4H-SiC JFET voltage continuation.

Place in the JFET_TCAD repository root. Does not call the legacy fixed
(-20 V, 200 V) prescribed-quasi-Fermi shortcut. Runs the coupled solver
for every requested point and independently checks the final transport state.

This is a research/diagnostic runner, NOT a certified avalanche/breakdown model.
"""
from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import math
import heapq
import json
from pathlib import Path
import platform
import subprocess
import sys
from typing import Any, Callable

import numpy as np

DEFAULT_BIASES = (0.0, 1.0, 5.0, 20.0, 50.0, 100.0, 200.0)


@dataclass
class Stage:
    bias_v: float
    psi: np.ndarray
    phi_n: np.ndarray
    fields: dict[str, np.ndarray]
    metrics: dict[str, Any]
    history: list[dict[str, Any]]


class StageFailure(RuntimeError):
    """The attempted voltage step did not pass numerical acceptance gates."""


def read_biases(s: str) -> list[float]:
    vals = [float(p.strip()) for p in s.split(",") if p.strip()]
    if not vals or any(not np.isfinite(v) or v < 0 for v in vals):
        raise ValueError("Drain biases must be finite, nonnegative, and nonempty")
    if vals[0] != 0.0 or vals != sorted(set(vals)):
        raise ValueError("Biases must start at 0 V and be strictly increasing")
    return vals


def bias_slug(bias_v: float) -> str:
    """Keep the version-1 NPZ filename scheme for backward-compatible recovery."""
    return f"{bias_v:.6f}".rstrip("0").rstrip(".").replace(".", "p")


def build_dense_schedule(base: list[float], *, zone_specs: list[str],
                         outer_max_step: float) -> list[float]:
    """Include all base targets and cap *every* proposed voltage step.

    Zones use START:END:MAX_STEP, e.g. 5:30:0.5. The caps are maximum
    increments, not assertions that any particular nonlinear solve succeeds.
    No unaccepted state is inserted as a warm start.
    """
    if not np.isfinite(outer_max_step) or outer_max_step <= 0:
        raise ValueError("outer_max_step must be positive and finite")
    if len(base) < 2 or base[0] != 0 or base != sorted(set(base)):
        raise ValueError("base targets must start at 0 and increase strictly")
    zones: list[tuple[float, float, float]] = []
    for spec in zone_specs:
        chunks = spec.split(":")
        if len(chunks) != 3:
            raise ValueError(f"invalid dense zone {spec!r}; expected START:END:STEP")
        a, b, step = map(float, chunks)
        if any(not np.isfinite(x) for x in (a,b,step)) or not (0 <= a < b <= base[-1]) or step <= 0:
            raise ValueError(f"invalid dense zone boundaries/step: {spec!r}")
        zones.append((a,b,step))
    zones.sort()
    if any(zones[i][0] < zones[i-1][1] for i in range(1,len(zones))):
        raise ValueError("dense zones may meet at a boundary, but not overlap")
    knots = sorted(set(base + [v for a,b,_ in zones for v in (a,b)]))
    result = [0.0]
    for a, b in zip(knots, knots[1:]):
        cap = outer_max_step
        for lo, hi, finer in zones:
            if a >= lo-1e-12 and b <= hi+1e-12:
                cap = min(cap, finer)
        n = max(1, math.ceil((b-a)/cap-1e-12))
        for i in range(1, n+1):
            v = round(a + (b-a)*i/n, 10)
            if v <= result[-1] + 1e-11:
                raise ValueError("schedule precision collapsed successive points")
            result.append(v)
    if abs(result[-1] - base[-1]) > 1e-9:
        raise AssertionError("last target changed")
    return result


def source_provenance(root: Path) -> dict[str, str]:
    files = [
        "src/device.py", "src/gummel.py", "src/transport.py",
        "src/poisson.py", "src/constants.py", "src/bernoulli.py",
        Path(__file__).name,
    ]
    hashes: dict[str, str] = {}
    for relative in files:
        path = root / relative
        if not path.is_file():
            raise FileNotFoundError(f"Missing solver source {path}")
        hashes[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    return hashes



def _scipy_version() -> str | None:
    try:
        import scipy
        return scipy.__version__
    except ImportError:
        return None


def _git_head(root: Path) -> str | None:
    """Record the checked-out commit when running inside a Git worktree."""
    try:
        result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root,
                                check=True, capture_output=True, text=True, timeout=5)
        return result.stdout.strip() or None
    except (OSError, subprocess.SubprocessError):
        return None

def load_resume_stages(previous_output: Path, grid: Any,
                       provenance: dict[str, Any], *, gate_v: float,
                       tol_v: float, floor_a_um: float) -> tuple[list[Stage], dict[str, Any]]:
    """Load a previous accepted sweep, refusing stale geometry and solver code.

    This verifies saved fields and metadata, not physical model fidelity.
    The final checkpoint is independently recomputed by the main routine.
    """
    path = previous_output / "CP06_summary.json"
    if not path.is_file():
        raise ValueError(f"missing resume summary: {path}")
    old_bytes = path.read_bytes()
    old = json.loads(old_bytes)
    pv = old.get("provenance", {})
    if old.get("foundation_override_used") or old.get("warnings"):
        raise ValueError("cannot certify resume from unverified foundation")
    for k in ("mesh_um", "pillar_um", "realized_gap_um", "realized_gate_depth_um",
              "gate_V", "tolerance_V", "current_floor_A_per_um"):
        if k not in pv or k not in provenance or not np.isclose(float(pv[k]), float(provenance[k]), rtol=0, atol=1e-12):
            raise ValueError(f"resume configuration mismatch: {k}")
    prior_hashes = pv.get("source_sha256", {})
    for relative, current_hash in provenance["source_sha256"].items():
        if not relative.startswith("src/"):
            continue   # runner revision intentionally allowed; solver source must match
        if prior_hashes.get(relative) != current_hash:
            raise ValueError(f"resume solver source SHA-256 differs: {relative}")
    rows = old.get("point_summaries", [])
    if not rows or len(rows) != old.get("accepted_points"):
        raise ValueError("resume accepted_points / rows are missing or inconsistent")
    stages = []
    prior_bias = -1.0
    for m in rows:
        v = float(m["VDS_V"])
        if not np.isfinite(v) or v <= prior_bias:
            raise ValueError("resume biases not finite and strictly increasing")
        prior_bias = v
        failures = validate_stage_metrics(m, tol_v=tol_v, balance_tol=1e-5)
        if failures:
            raise ValueError(f"resume point {v:g} fails stage gates: {failures}")
        data_path = previous_output / f"CP06_VDS_{bias_slug(v)}V_fields.npz"
        if not data_path.is_file():
            raise ValueError(f"missing restart NPZ for accepted voltage {v}: {data_path}")
        with np.load(data_path, allow_pickle=False) as npz:
            fields = {k: npz[k].copy() for k in npz.files}
        required = ("psi_V", "phi_n_V", "x_um", "y_um", "gate_mask", "active_mask")
        if any(k not in fields for k in required):
            raise ValueError(f"missing required restart fields at {v:g} V")
        for name in ("psi_V", "phi_n_V"):
            if fields[name].shape != grid.active_mask.shape or not np.all(np.isfinite(fields[name][grid.active_mask])):
                raise ValueError(f"bad restart {name} at {v:g} V")
        if (not np.array_equal(fields["gate_mask"], grid.gate_mask) or
            not np.array_equal(fields["active_mask"], grid.active_mask) or
            not np.array_equal(fields["x_um"], grid.x_um) or
            not np.array_equal(fields["y_um"], grid.y_um)):
            raise ValueError(f"restart geometry or coordinates changed at {v:g} V")
        histfile = previous_output / f"CP06_VDS_{bias_slug(v)}V_history.csv"
        hist = []
        if histfile.is_file():
            with histfile.open(newline="", encoding="utf-8") as f:
                hist = list(csv.DictReader(f))
        stages.append(Stage(v, fields["psi_V"].copy(), fields["phi_n_V"].copy(),
                            fields, dict(m), hist))
    if abs(stages[0].bias_v) > 1e-12 or not np.isclose(old["last_accepted_bias_V"], stages[-1].bias_v):
        raise ValueError("restart baseline / last accepted stage inconsistent")
    previous_info = {
        "prior_run_summary_sha256": hashlib.sha256(old_bytes).hexdigest(),
        "prior_output_directory": str(previous_output.resolve()),
        "prior_runner_sha256": {k:v for k,v in prior_hashes.items() if not k.startswith("src/")},
        "reused_stage_count": len(stages),
        "reused_through_V": stages[-1].bias_v,
    }
    return stages, previous_info


def foundation_warnings(root: Path) -> list[str]:
    """Fail-closed checks for identifiable problems in the publicly visible main.

    These checks do NOT certify the physics. They only detect known blockers.
    """
    g = (root / "src/gummel.py").read_text(encoding="utf-8")
    d = (root / "src/device.py").read_text(encoding="utf-8")
    p = (root / "src/poisson.py").read_text(encoding="utf-8")
    warnings = []
    if "max_cell_e_mv_cm * 1.15" in g:
        warnings.append("Gummel still contains artificial 15% gate-field multiplier")
    if "np.max(center_potential) - center_potential[0]" in g:
        warnings.append("Gummel still uses drain-dominated centerline barrier")
    if "gate_y0_um + gate_y1_um" in d and "gate_y1_um =" not in d:
        warnings.append("bipolar_full still references undefined gate_y1_um")
    if "-70.0, 30.0" in p:
        warnings.append("Poisson retains old exp(30) carrier-density ceiling")
    return warnings


def minimax_path_barrier(psi: np.ndarray, active: np.ndarray,
                        source: np.ndarray, drain: np.ndarray,
                        x_um: np.ndarray, y_um: np.ndarray) -> dict[str, float]:
    """Electrostatic conduction-band bottleneck along a connected path.

    Constant-affinity/band model: (Ec - Ec_source)/q = psi_source - psi in V,
    numerically equal to eV for a singly charged electron. Minimizes the
    *maximum* positive elevation over all connected active-cell paths.
    This is a physically interpretable proxy, NOT a full injection barrier.
    """
    if psi.ndim != 2 or any(a.shape != psi.shape for a in (active, source, drain)):
        raise ValueError("Potential and masks must have identical 2D shapes")
    if not np.any(source & active) or not np.any(drain & active):
        raise ValueError("At least one active source and drain cell is required")
    if np.any(~np.isfinite(psi[active])):
        raise ValueError("Nonfinite potential in active region")
    ny, nx = psi.shape
    psi_source = float(np.median(psi[source & active]))
    height = np.maximum(psi_source - psi, 0.0)
    best = np.full((ny, nx), np.inf)
    predecessor = np.full((ny, nx), -1, dtype=np.int64)
    queue: list[tuple[float, int]] = []
    for flat in np.flatnonzero(source & active):
        j, i = divmod(int(flat), nx)
        best[j, i] = float(height[j, i])
        heapq.heappush(queue, (best[j, i], int(flat)))
    destination = None
    while queue:
        candidate, flat = heapq.heappop(queue)
        j, i = divmod(flat, nx)
        if candidate > best[j, i]:
            continue
        if drain[j, i]:
            destination = flat
            break
        for j2, i2 in ((j - 1, i), (j + 1, i), (j, i - 1), (j, i + 1)):
            if not (0 <= j2 < ny and 0 <= i2 < nx and active[j2, i2]):
                continue
            alt = max(candidate, float(height[j2, i2]))
            if alt < best[j2, i2]:
                best[j2, i2] = alt
                predecessor[j2, i2] = flat
                heapq.heappush(queue, (alt, j2 * nx + i2))
    if destination is None:
        raise ValueError("No active path connects source and drain")
    path: list[int] = []
    flat = destination
    while flat >= 0:
        path.append(flat)
        flat = int(predecessor.flat[flat])
    bottleneck = max(path, key=lambda k: float(height.flat[k]))
    j, i = divmod(bottleneck, nx)
    return {
        "barrier_proxy_eV": float(best.flat[destination]),
        "bottleneck_x_um": float(x_um[i]),
        "bottleneck_y_um": float(y_um[j]),
        "source_psi_V": psi_source,
        "path_cells": len(path),
    }


def current_resolution(source_a_um: float, drain_a_um: float,
                       edge_source_a_m2: np.ndarray,
                       edge_drain_a_m2: np.ndarray,
                       dx_m: float,
                       floor_a_um: float) -> dict[str, float | bool]:
    """Conservative numerical resolution flag; not a physical leakage estimate."""
    currents = (float(source_a_um), float(drain_a_um))
    if any(not np.isfinite(x) for x in currents):
        raise ValueError("Nonfinite terminal currents")
    mismatch = abs(sum(currents))
    maximum = max(map(abs, currents))
    floating_floor = (
        100.0 * np.finfo(float).eps * dx_m * 1e-6
        * float(np.sum(np.abs(edge_source_a_m2)) + np.sum(np.abs(edge_drain_a_m2)))
    )
    threshold = max(floor_a_um, floating_floor, 100.0 * mismatch)
    relative = mismatch / maximum if maximum > 0 else None
    return {
        "terminal_imbalance_abs_A_per_um": mismatch,
        "terminal_balance_relative": relative,
        "floating_roundoff_floor_A_per_um": floating_floor,
        "current_resolution_floor_A_per_um": threshold,
        "current_resolved": maximum > threshold,
    }


def local_continuity_diagnostics(grid: Any, jx_a_m2: np.ndarray,
                                 jy_a_m2: np.ndarray) -> dict[str, float]:
    """Finite-volume continuity imbalance on free nodes, using shared face flux.

    Returns absolute node-net [A/m out-of-plane width] and a dimensionless
    maximum-norm scaled by the largest absolute per-node face throughput.
    This global normalization avoids dividing by numerically tiny local fluxes.
    """
    dx = grid.dx_um * 1e-6
    dy = grid.dy_um * 1e-6
    right = jx_a_m2 * dy
    down = jy_a_m2 * dx
    left = np.zeros_like(right)
    up = np.zeros_like(down)
    left[:, 1:] = right[:, :-1]
    up[1:, :] = down[:-1, :]
    net = right - left + down - up
    throughput = np.abs(right) + np.abs(left) + np.abs(down) + np.abs(up)
    free = grid.active_mask & ~grid.source_mask & ~grid.drain_mask
    if not np.any(free):
        return {"local_continuity_max_A_per_m": 0.0,
                "local_continuity_relative": 0.0}
    max_absolute = float(np.max(np.abs(net[free])))
    max_throughput = float(np.max(throughput[free]))
    return {"local_continuity_max_A_per_m": max_absolute,
            "local_continuity_relative": max_absolute / max(max_throughput, 1e-30)}


def local_continuity_norm(grid: Any, jx_a_m2: np.ndarray,
                          jy_a_m2: np.ndarray) -> float:
    """Backward-compatible absolute continuity diagnostic [A/m]."""
    return local_continuity_diagnostics(grid, jx_a_m2, jy_a_m2)["local_continuity_max_A_per_m"]


def validate_stage_metrics(metrics: dict, *, tol_v: float,
                           balance_tol: float) -> list[str]:
    reasons = []
    if not metrics.get("gummel_converged", False):
        reasons.append("Gummel iteration did not converge")
    for name in ("independent_poisson_residual_V", "independent_correction_V"):
        val = float(metrics.get(name, np.inf))
        if not np.isfinite(val) or val >= tol_v:
            reasons.append(f"{name}={val} exceeds {tol_v}")
    if not metrics.get("finite_positive_density", False):
        reasons.append("Nonfinite/nonpositive electron density")
    balance = metrics.get("terminal_balance_relative")
    # Balance ratio meaningful only if current itself is numerically resolved.
    if metrics.get("current_resolved", False):
        if balance is None or not np.isfinite(balance) or balance >= balance_tol:
            reasons.append(f"Resolved terminal imbalance {balance} exceeds {balance_tol}")
        local_relative = float(metrics.get("local_continuity_relative", np.inf))
        if not np.isfinite(local_relative) or local_relative >= balance_tol:
            reasons.append(f"Local continuity residual {local_relative} exceeds {balance_tol}")
    return reasons


def analyze_stage(grid: Any, gate_v: float, bias_v: float, psi: np.ndarray,
                  gummel_metrics: dict, history: list[dict],
                  *, tol_v: float, floor_a_um: float) -> Stage:
    # Import only when actually running inside repository.
    from src.poisson import FastPoissonSolver
    from src.transport import FastTransportSolver

    transport = FastTransportSolver(grid)
    n_m3, phi_n, jx_a_m2, jy_a_m2, currents = transport.solve_step(
        psi=psi, v_gate=gate_v, v_drain=bias_v, v_source=0.0
    )
    if np.any(~np.isfinite(n_m3)) or np.any(~np.isfinite(phi_n)):
        raise StageFailure("Nonfinite density/quasi-Fermi potential after transport")
    if np.any(n_m3[grid.active_mask] <= 0):
        raise StageFailure("Nonpositive active electron density")
    # Verify Poisson on FINAL potential and transport-derived quasi-Fermi state.
    _, _, p_res, p_corr = FastPoissonSolver(grid).solve_step(
        psi=psi, phi_n=phi_n, v_gate=gate_v,
        v_drain=bias_v, v_source=0.0
    )
    if np.any(~np.isfinite(psi[grid.active_mask])):
        raise StageFailure("Nonfinite electrostatic potential")
    resolution = current_resolution(
        currents["source_A_per_um"], currents["drain_A_per_um"],
        jy_a_m2[0, :], jy_a_m2[-2, :], grid.dx_um * 1e-6, floor_a_um
    )
    barrier = minimax_path_barrier(
        psi, grid.active_mask, grid.source_mask, grid.drain_mask,
        grid.x_um, grid.y_um
    )
    # A face-interpolated current visualization must NOT replace the edge flux.
    ey, ex = np.gradient(-psi, grid.dy_um * 1e-4, grid.dx_um * 1e-4)
    field_magnitude = np.hypot(ex, ey)
    metrics: dict[str, Any] = {
        "VGS_V": float(gate_v),
        "VDS_V": float(bias_v),
        "gummel_converged": bool(gummel_metrics.get("converged", False)),
        "gummel_iterations": int(gummel_metrics.get("iterations", 0)),
        "independent_poisson_residual_V": float(p_res),
        "independent_correction_V": float(p_corr),
        "source_A_per_um": float(currents["source_A_per_um"]),
        "drain_A_per_um": float(currents["drain_A_per_um"]),
        "finite_positive_density": bool(np.all(np.isfinite(n_m3[grid.active_mask]))
                                        and np.all(n_m3[grid.active_mask] > 0)),
        **local_continuity_diagnostics(grid, jx_a_m2, jy_a_m2),
        "max_cell_field_MV_per_cm": float(np.max(field_magnitude[grid.active_mask]) / 1e6),
        "phi_n_recovered_from_final_transport": True,
        "barrier_model": "2D minimax electrostatic Ec proxy, not full injection barrier",
        **resolution,
        **barrier,
    }
    fields = {
        "x_um": grid.x_um, "y_um": grid.y_um,
        "psi_V": psi, "phi_n_V": phi_n,
        "electron_density_cm3": n_m3 * 1e-6,
        "Jx_A_per_cm2": jx_a_m2 * 1e-4,
        "Jy_A_per_cm2": jy_a_m2 * 1e-4,
        "Ex_V_per_cm": ex,
        "Ey_V_per_cm": ey,
        "gate_mask": grid.gate_mask,
        "active_mask": grid.active_mask,
    }
    return Stage(bias_v, psi.copy(), phi_n.copy(), fields, metrics, history)


def execute_continuation(
    targets: list[float],
    solve_stage: Callable[[float, Stage | None], Stage],
    accept_stage: Callable[[Stage], list[str]],
    *, min_step: float = 0.25, max_refinements: int = 100,
    initial_accepted: list[Stage] | None = None
) -> tuple[list[Stage], list[dict[str, Any]], str]:
    """Adaptively bisect FAILED steps while keeping the last accepted state.

    Checkpoint handoff is only from a fully accepted stage; failed candidates
    are not persisted as valid solutions or used as warm starts.
    """
    accepted: list[Stage] = list(initial_accepted or [])
    last_seed = accepted[-1].bias_v if accepted else -np.inf
    pending = [v for v in targets if v > last_seed + 1e-10]
    attempts: list[dict[str, Any]] = []
    refinements = 0
    outcome = "COMPLETE"
    while pending:
        requested = pending.pop(0)
        previous = accepted[-1] if accepted else None
        try:
            candidate = solve_stage(requested, previous)
            problems = accept_stage(candidate)
        except (StageFailure, ValueError, FloatingPointError,
                RuntimeError, ArithmeticError) as exc:
            candidate = None
            problems = [f"{type(exc).__name__}: {exc}"]
        attempt = {"VDS_V": requested, "accepted": not problems, "problems": problems}
        attempts.append(attempt)
        if not problems:
            accepted.append(candidate)
            continue
        if (previous is None or refinements >= max_refinements or
                requested - previous.bias_v <= min_step):
            outcome = "BLOCKED"
            break
        middle = 0.5 * (previous.bias_v + requested)
        refinements += 1
        pending.insert(0, requested)
        pending.insert(0, middle)
    return accepted, attempts, outcome


def summarize(accepted: list[Stage], targets: list[float], status: str,
              *, warnings: list[str], forced: bool) -> dict[str, Any]:
    rows = [s.metrics for s in accepted]
    baseline = next((s.metrics["barrier_proxy_eV"] for s in accepted if s.bias_v == 0), None)
    for s in accepted:
        s.metrics["barrier_drop_from_0V_eV"] = (
            float(baseline - s.metrics["barrier_proxy_eV"]) if baseline is not None else None
        )
    at_200 = next((s for s in accepted if abs(s.bias_v - 200) < 1e-10), None)
    target_coverage = all(any(abs(s.bias_v - v) <= 1e-9 for s in accepted)
                          for v in targets)
    cp06_numerical = (
        "PASS" if status == "COMPLETE" and target_coverage and at_200 is not None
        and at_200.metrics.get("current_resolved", False)
        and at_200.metrics.get("barrier_drop_from_0V_eV", 0) > 0
        and not warnings and not forced
        else "NOT_ESTABLISHED"
    )
    return {
        "continuation_status": status,
        "requested_targets_covered": target_coverage,
        "CP06_numerical_transport": cp06_numerical,
        "CP06_paper_reproduction": "PENDING_INDEPENDENT_VALIDATION",
        "warnings": warnings,
        "foundation_override_used": forced,
        "planned_targets_V": targets,
        "accepted_points": len(accepted),
        "last_accepted_bias_V": accepted[-1].bias_v if accepted else None,
        "baseline_barrier_proxy_eV": baseline,
        "point_summaries": rows,
    }


def export_results(output: Path, accepted: list[Stage], attempts: list[dict],
                   summary: dict, provenance: dict, *, save_fields: str) -> None:
    output.mkdir(parents=True, exist_ok=True)
    rows = summary["point_summaries"]
    if rows:
        fieldnames = list(rows[0])
        with (output / "CP06_points.csv").open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(rows)
    with (output / "CP06_attempts.json").open("w", encoding="utf-8") as f:
        json.dump(attempts, f, indent=2)
    with (output / "CP06_summary.json").open("w", encoding="utf-8") as f:
        json.dump({**summary, "provenance": provenance}, f, indent=2)
    saves = accepted if save_fields == "all" else (accepted[-1:] if save_fields == "final" else [])
    for s in saves:
        slug = bias_slug(s.bias_v)
        np.savez_compressed(output / f"CP06_VDS_{slug}V_fields.npz", **s.fields)
        with (output / f"CP06_VDS_{slug}V_history.csv").open("w", newline="", encoding="utf-8") as f:
            if s.history:
                writer = csv.DictWriter(f, fieldnames=list(s.history[0]))
                writer.writeheader()
                writer.writerows(s.history)


def make_plots(output: Path, stages: list[Stage]):
    if not stages:
        return
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    x = [s.bias_v for s in stages]
    ids = [abs(s.metrics["drain_A_per_um"]) for s in stages]
    barriers = [s.metrics["barrier_proxy_eV"] for s in stages]
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogy(x, np.maximum(ids, 1e-30), "o-")
    ax.set_xlabel("Drain voltage VDS (V)")
    ax.set_ylabel("|Id| (A per micrometer device width)")
    ax.set_title("CP06: Solved electron current (not avalanche)")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output / "CP06_Id_VDS.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.plot(x, barriers, "o-")
    ax.set_xlabel("Drain voltage VDS (V)")
    ax.set_ylabel("2D minimax Ec barrier proxy (eV)")
    ax.set_title("CP06: source-referenced path barrier")
    ax.grid(True, alpha=0.3)
    fig.tight_layout()
    fig.savefig(output / "CP06_barrier_VDS.png", dpi=180)
    plt.close(fig)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--mesh", type=float, default=0.2)
    ap.add_argument("--gate", type=float, default=-20.0)
    ap.add_argument("--pillar", type=float, default=2.2)
    ap.add_argument("--gap", type=float, default=1.8)
    ap.add_argument("--gate-depth", type=float, default=0.6)
    ap.add_argument("--biases", default=",".join(str(v) for v in DEFAULT_BIASES))
    ap.add_argument("--max-outer", type=int, default=1500)
    ap.add_argument("--tol", type=float, default=1.9e-6)
    ap.add_argument("--inner-factor", type=float, default=0.75,
                    help="factor to tighten inner Gummel tolerance relative to --tol (default 0.75)")
    ap.add_argument("--damping", type=float, default=0.65)
    ap.add_argument("--current-floor", type=float, default=1e-12,
                    help="conservative current resolution floor [A/um], not leakage")
    ap.add_argument("--min-step", type=float, default=0.25)
    ap.add_argument("--max-refinements", type=int, default=100)
    ap.add_argument("--outer-max-step", type=float, default=5.0,
                    help="maximum proposed step outside dense zones [V]")
    ap.add_argument("--dense-zone", action="append", default=None,
                    help="repeatable START:END:STEP; default 5:30:0.5")
    ap.add_argument("--resume-from", type=Path, default=None,
                    help="previous nonempty CP06 directory with all accepted field NPZs")
    ap.add_argument("--save-fields", choices=("all", "final", "none"), default="all")
    ap.add_argument("--output", default="runs/CP06_continuation")
    ap.add_argument("--force-unverified-foundation", action="store_true",
                    help="exploratory only; CP06 numerical PASS disabled")
    args = ap.parse_args()
    if args.mesh <= 0 or args.tol <= 0 or args.current_floor < 0 or not (0 < args.damping <= 1):
        ap.error("Invalid positive mesh/tolerance/floor/damping configuration")
    bases = read_biases(args.biases)
    if args.min_step <= 0 or args.max_refinements < 0 or args.max_outer <= 0:
        ap.error("Invalid continuation or solver step limits")
    try:
        biases = build_dense_schedule(bases, zone_specs=(args.dense_zone if args.dense_zone is not None else ["5:30:0.5"]),
                                      outer_max_step=args.outer_max_step)
    except ValueError as exc:
        ap.error(str(exc))
    root = Path(__file__).resolve().parent
    hashes = source_provenance(root)
    warnings = foundation_warnings(root)
    if warnings and not args.force_unverified_foundation:
        print("BLOCKED: Step 1 source blockers detected:\n - " + "\n - ".join(warnings), file=sys.stderr)
        print("Use the verified Step 1 commit/branch. --force-unverified-foundation is exploratory only.",
              file=sys.stderr)
        return 2
    from src.device import create_jfet_device
    from src.gummel import run_gummel_loop
    grid = create_jfet_device(
        mesh_spacing_um=args.mesh,
        pillar_width_um=args.pillar, gate_gap_um=args.gap,
        gate_depth_um=args.gate_depth,
        total_height_um=13.0,
        mode="equipotential_gate",
    )
    # CP05 is geometric, not mesh-independent. Enforce intended realized dimensions.
    gap_error = abs(grid.gate_gap_um - args.gap)
    depth_error = abs(grid.gate_depth_um - args.gate_depth)
    if (gap_error > 1e-9 or depth_error > 1e-9 or
            not np.array_equal(grid.gate_mask, grid.gate_mask[:, ::-1])):
        print("BLOCKED CP05 geometry: realized gap/depth/mirror symmetry mismatch", file=sys.stderr)
        return 2
    output = Path(args.output)
    if output.exists() and any(output.iterdir()):
        print("Refusing to overwrite existing results. Choose a new --output directory.", file=sys.stderr)
        return 2
    provenance = {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "numpy": np.__version__,
        "scipy": _scipy_version(),
        "source_sha256": hashes,
        "git_head": _git_head(root),
        "mesh_um": args.mesh,
        "pillar_um": args.pillar,
        "outer_max_step_V": args.outer_max_step,
        "dense_zones": (args.dense_zone if args.dense_zone is not None else ["5:30:0.5"]),
        "realized_gap_um": grid.gate_gap_um,
        "realized_gate_depth_um": grid.gate_depth_um,
        "gate_V": args.gate,
        "tolerance_V": args.tol,
        "current_floor_A_per_um": args.current_floor,
    }

    seed: list[Stage] = []
    if args.resume_from is not None:
        try:
            seed, previous_info = load_resume_stages(args.resume_from, grid, provenance,
                                                       gate_v=args.gate, tol_v=args.tol,
                                                       floor_a_um=args.current_floor)
            # Recompute final state from live solver - do not blindly trust saved metrics.
            previous = seed[-1]
            recomputed = analyze_stage(grid, args.gate, previous.bias_v, previous.psi,
                                       {"converged": True, "iterations": previous.metrics.get("gummel_iterations", 0)},
                                       previous.history, tol_v=args.tol,
                                       floor_a_um=args.current_floor)
            issues = validate_stage_metrics(recomputed.metrics, tol_v=args.tol, balance_tol=1e-5)
            if issues:
                raise ValueError(f"live recomputation of restart state failed: {issues}")
            diff = abs(recomputed.metrics["barrier_proxy_eV"] - previous.metrics["barrier_proxy_eV"])
            if diff > max(1e-8, abs(previous.metrics["barrier_proxy_eV"])*1e-7):
                raise ValueError(f"restart barrier does not replay: {diff:g} eV")
            if (bool(recomputed.metrics["current_resolved"]) != bool(previous.metrics["current_resolved"])):
                raise ValueError("restart current-resolution status not reproducible")
            seed[-1] = recomputed
            provenance["resume"] = previous_info
            print(f"Validated CP06 checkpoint through {seed[-1].bias_v:g} V; "
                  f"reusing {len(seed)} accepted stages")
        except (ValueError, KeyError, OSError, StageFailure) as exc:
            print(f"BLOCKED restart: {exc}", file=sys.stderr)
            return 2

    def solve(bias: float, previous: Stage | None) -> Stage:
        inner_tol = args.inner_factor * args.tol
        psi, _, metrics, history = run_gummel_loop(
            grid=grid, v_gate=args.gate, v_drain=bias, v_source=0.0,
            max_outer_iter=args.max_outer, tol_residual_v=inner_tol,
            tol_correction_v=inner_tol, damping_factor=args.damping,
            psi_init=previous.psi if previous else None,
            phi_n_init=previous.phi_n if previous else None,
        )
        return analyze_stage(grid, args.gate, bias, psi, metrics, history,
                             tol_v=args.tol, floor_a_um=args.current_floor)

    def accept(stage: Stage) -> list[str]:
        return validate_stage_metrics(stage.metrics, tol_v=args.tol, balance_tol=1e-5)

    run_targets = [v for v in biases if not seed or v > seed[-1].bias_v + 1e-10]
    accepted, attempts, status = execute_continuation(
        run_targets, solve, accept, min_step=args.min_step,
        max_refinements=args.max_refinements, initial_accepted=seed,
    )
    summary = summarize(accepted, run_targets if seed else biases, status,
                        warnings=warnings, forced=args.force_unverified_foundation)
    summary["full_dense_schedule_V"] = biases
    summary["reused_stage_count"] = len(seed)
    export_results(output, accepted, attempts, summary, provenance,
                   save_fields=args.save_fields)
    make_plots(output, accepted)
    print(json.dumps({k: v for k, v in summary.items()
                      if k not in ("point_summaries", "full_dense_schedule_V")}, indent=2))
    return 0 if status == "COMPLETE" else 1


if __name__ == "__main__":
    raise SystemExit(main())
