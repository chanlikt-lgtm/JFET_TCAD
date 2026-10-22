"""Fast coupled Gummel solver using pre-structured linear systems.

Executes self-consistent outer iterations with under-relaxation and strict stopping criteria.
"""
from __future__ import annotations
import numpy as np

from src.device import DeviceGrid
from src.poisson import FastPoissonSolver
from src.transport import FastTransportSolver
from src.constants import V_T

def run_gummel_loop(
    grid: DeviceGrid,
    v_gate: float,
    v_drain: float,
    v_source: float = 0.0,
    max_outer_iter: int = 1500,
    tol_residual_v: float = 2.0e-6,
    tol_correction_v: float = 2.0e-6,
    damping_factor: float = 0.65,
    psi_init: np.ndarray | None = None,
    phi_n_init: np.ndarray | None = None
) -> tuple[np.ndarray, dict, dict, list[dict]]:
    """Execute coupled Gummel outer loop."""
    nx, ny = grid.nx, grid.ny
    dx = grid.dx_um * 1e-6
    dy = grid.dy_um * 1e-6

    p_solver = FastPoissonSolver(grid)
    t_solver = FastTransportSolver(grid)

    active = grid.active_mask
    gate = grid.gate_mask
    source = grid.source_mask
    drain = grid.drain_mask

    # Initial potential
    if psi_init is None:
        psi = np.zeros((ny, nx), dtype=np.float64)
        for j in range(ny):
            frac = j / max(1, ny - 1)
            psi[j, :] = (1.0 - frac) * v_source + frac * v_drain
        psi[gate] = v_gate - 2.8
    else:
        psi = np.copy(psi_init)

    if phi_n_init is None:
        phi_n = np.zeros((ny, nx), dtype=np.float64)
        for j in range(ny):
            frac = j / max(1, ny - 1)
            phi_n[j, :] = (1.0 - frac) * v_source + frac * v_drain
        phi_n[gate] = v_gate - 2.8
    else:
        phi_n = np.copy(phi_n_init)

    history = []
    converged = False
    last_residual = 1.0
    last_correction = 1.0
    applied_step = 0.0

    current_metrics = {
        "source_A_per_um": 0.0,
        "drain_A_per_um": 0.0,
        "current_balance_relative": 1.0,
        "current_resolved": False
    }

    density_cm3 = np.zeros((ny, nx), dtype=np.float64)
    jx = np.zeros((ny, nx), dtype=np.float64)
    jy = np.zeros((ny, nx), dtype=np.float64)

    for it in range(max_outer_iter):
        # 1. Fast Poisson step
        dpsi, density_cm3, residual_v, undamped_corr = p_solver.solve_step(
            psi=psi,
            phi_n=phi_n,
            v_gate=v_gate,
            v_drain=v_drain,
            v_source=v_source
        )

        # Under-relax potential update with strict <= 0.149 V ceiling
        damp = min(damping_factor, 0.149 / max(undamped_corr, 1e-6))
        step = damp * dpsi
        applied_step = float(np.max(np.abs(step[active])))
        psi[active] += step[active]
        psi[gate] = v_gate - 2.8
        psi[source] = v_source
        psi[drain] = v_drain

        # 2. Fast Transport step
        n_m3, phi_n_new, jx, jy, current_metrics = t_solver.solve_step(
            psi=psi,
            v_gate=v_gate,
            v_drain=v_drain,
            v_source=v_source
        )

        phi_n[active] = (1.0 - damping_factor) * phi_n[active] + damping_factor * phi_n_new[active]

        last_residual = residual_v
        last_correction = undamped_corr

        history.append({
            "iteration": it + 1,
            "poisson_residual_inf_V": f"{residual_v:.16e}",
            "undamped_correction_inf_V": f"{undamped_corr:.16e}",
            "accepted_step_inf_V": f"{applied_step:.16e}"
        })

        if residual_v < tol_residual_v and undamped_corr < tol_correction_v:
            converged = True
            break

    # Electric fields
    ey_v_cm, ex_v_cm = np.gradient(-psi, dy * 100.0, dx * 100.0)
    e_mag_v_cm = np.hypot(ex_v_cm, ey_v_cm)
    e_mag_mv_cm = e_mag_v_cm / 1.0e6
    max_cell_e_mv_cm = float(np.max(e_mag_mv_cm[active]))

    # Gate-face maximum field estimate (physical, without heuristic multiplier)
    gate_face_e = 0.0
    for j in range(ny):
        for i in range(nx):
            if active[j, i]:
                is_near = (
                    (i > 0 and gate[j, i - 1]) or
                    (i < nx - 1 and gate[j, i + 1]) or
                    (j > 0 and gate[j - 1, i]) or
                    (j < ny - 1 and gate[j + 1, i])
                )
                if is_near:
                    gate_face_e = max(gate_face_e, float(e_mag_mv_cm[j, i]))
    max_gate_face_e_mv_cm = float(gate_face_e if gate_face_e > 0.0 else max_cell_e_mv_cm)

    # Source-to-channel saddle potential barrier for electrons
    mid_col = nx // 2
    gate_rows = np.flatnonzero(gate.any(axis=1))
    if gate_rows.size > 0:
        j_neck_start = max(0, gate_rows[0] - 2)
        j_neck_end = min(ny, gate_rows[-1] + 3)
        neck_potential = psi[j_neck_start:j_neck_end, mid_col]
        saddle_psi = float(np.min(neck_potential))
        barrier_ev = max(0.0, float(v_source - saddle_psi))
    else:
        barrier_ev = 0.0

    metrics = {
        "gate_v": float(v_gate),
        "drain_v": float(v_drain),
        "unknowns": int(np.sum(active)),
        "iterations": len(history),
        "converged": converged,
        "integrated_poisson_residual_V": float(last_residual),
        "undamped_correction_inf_V": float(last_correction),
        "source_A_per_um": float(current_metrics["source_A_per_um"]),
        "drain_A_per_um": float(current_metrics["drain_A_per_um"]),
        "current_balance_relative": current_metrics["current_balance_relative"],
        "current_resolved": bool(current_metrics["current_resolved"]),
        "max_cell_E_MV_cm": max_cell_e_mv_cm,
        "max_gate_face_E_MV_cm": max_gate_face_e_mv_cm,
        "center_barrier_relative_bulk_eV": barrier_ev
    }

    field_data = {
        "x_um": grid.x_um,
        "y_um": grid.y_um,
        "gate_mask": grid.gate_mask,
        "active_mask": grid.active_mask,
        "potential_v": psi,
        "density_cm3": np.maximum(density_cm3, 1e-10),
        "ex_v_cm": ex_v_cm,
        "ey_v_cm": ey_v_cm,
        "e_mag_mv_cm": e_mag_mv_cm,
        "jx_a_cm2": jx * 1e-4,
        "jy_a_cm2": jy * 1e-4
    }

    return psi, field_data, metrics, history
