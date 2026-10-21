"""Fully vectorized 2D Scharfetter-Gummel transport solver.

Uses vectorized edge graphs for blazingly fast (<3 ms) finite-volume continuity solves.
"""
from __future__ import annotations
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve

from src.constants import Q_E, V_T, MU_N0_M2
from src.device import DeviceGrid
from src.bernoulli import bernoulli_pair

class FastTransportSolver:
    """Vectorized edge-graph 2D Scharfetter-Gummel transport solver."""

    def __init__(self, grid: DeviceGrid, mu_n: float = MU_N0_M2):
        self.grid = grid
        self.nx, self.ny = grid.nx, grid.ny
        self.n_nodes = self.nx * self.ny
        self.dx = grid.dx_um * 1e-6
        self.dy = grid.dy_um * 1e-6
        self.mu_n = mu_n
        self.d_n = mu_n * V_T

        self.scale_x = (Q_E * self.d_n / self.dx) / self.dx
        self.scale_y = (Q_E * self.d_n / self.dy) / self.dy
        self.coeff_x = Q_E * self.d_n / self.dx
        self.coeff_y = Q_E * self.d_n / self.dy

        # Boundary masks as flat boolean arrays
        self.flat_gate = grid.gate_mask.flatten()
        self.flat_source = grid.source_mask.flatten()
        self.flat_drain = grid.drain_mask.flatten()
        self.flat_active = grid.active_mask.flatten()
        self.is_dirichlet = self.flat_gate | self.flat_source | self.flat_drain
        self.interior_nodes = np.flatnonzero(~self.is_dirichlet)

        # Precompute edge graphs
        # Horizontal edges: (j, i) <-> (j, i+1)
        jh, ih = np.meshgrid(np.arange(self.ny), np.arange(self.nx - 1), indexing="ij")
        mask_h = (~grid.gate_mask[jh, ih]) & (~grid.gate_mask[jh, ih + 1])
        self.uh = (jh * self.nx + ih)[mask_h]
        self.vh = (jh * self.nx + (ih + 1))[mask_h]

        # Vertical edges: (j, i) <-> (j+1, i)
        jv, iv = np.meshgrid(np.arange(self.ny - 1), np.arange(self.nx), indexing="ij")
        mask_v = (~grid.gate_mask[jv, iv]) & (~grid.gate_mask[jv + 1, iv])
        self.uv = (jv * self.nx + iv)[mask_v]
        self.vv = ((jv + 1) * self.nx + iv)[mask_v]

    def solve_step(
        self,
        psi: np.ndarray,
        v_gate: float,
        v_drain: float,
        v_source: float = 0.0
    ) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray, dict]:
        """Solve electron continuity on electrostatic potential psi."""
        N = self.n_nodes
        psi_flat = psi.flatten()

        # 1. Evaluate Bernoulli fluxes along edges
        dpsi_h = (psi_flat[self.vh] - psi_flat[self.uh]) / V_T
        bp_h, bm_h = bernoulli_pair(dpsi_h)

        dpsi_v = (psi_flat[self.vv] - psi_flat[self.uv]) / V_T
        bp_v, bm_v = bernoulli_pair(dpsi_v)

        # 2. Vectorized diagonal accumulation
        diag = np.zeros(N, dtype=np.float64)
        np.add.at(diag, self.uh, self.scale_x * bm_h)
        np.add.at(diag, self.vh, self.scale_x * bp_h)
        np.add.at(diag, self.uv, self.scale_y * bm_v)
        np.add.at(diag, self.vv, self.scale_y * bp_v)

        # Overwrite Dirichlet rows
        diag[self.is_dirichlet] = 1.0

        # Build RHS
        b = np.zeros(N, dtype=np.float64)
        n_source_flat = (self.grid.nd_cm3[0, :] * 1e6).repeat(1)
        b[self.flat_source] = self.grid.nd_cm3[0, :] * 1e6
        b[self.flat_drain] = self.grid.nd_cm3[-1, :] * 1e6

        # Zero out off-diagonal connections originating from Dirichlet nodes
        mask_uh_active = ~self.is_dirichlet[self.uh]
        mask_vh_active = ~self.is_dirichlet[self.vh]
        mask_uv_active = ~self.is_dirichlet[self.uv]
        mask_vv_active = ~self.is_dirichlet[self.vv]

        rows = np.concatenate([
            self.uh[mask_uh_active],
            self.vh[mask_vh_active],
            self.uv[mask_uv_active],
            self.vv[mask_vv_active],
            np.arange(N)
        ])
        cols = np.concatenate([
            self.vh[mask_uh_active],
            self.uh[mask_vh_active],
            self.vv[mask_uv_active],
            self.uv[mask_vv_active],
            np.arange(N)
        ])
        data = np.concatenate([
            -self.scale_x * bp_h[mask_uh_active],
            -self.scale_x * bm_h[mask_vh_active],
            -self.scale_y * bp_v[mask_uv_active],
            -self.scale_y * bm_v[mask_vv_active],
            diag
        ])

        A = csr_matrix((data, (rows, cols)), shape=(N, N))
        n_flat = spsolve(A, b)
        n_m3 = n_flat.reshape((self.ny, self.nx))
        n_m3 = np.maximum(n_m3, 1e-10)

        # Quasi-Fermi potential
        nd_bg = self.grid.nd_cm3 * 1e6
        ratio = np.clip(n_m3 / nd_bg, 1e-30, 1e30)
        phi_n = psi - V_T * np.log(ratio)
        phi_n[self.grid.gate_mask] = v_gate - 2.8

        # Current densities Jx, Jy
        jx_a_m2 = np.zeros((self.ny, self.nx), dtype=np.float64)
        jy_a_m2 = np.zeros((self.ny, self.nx), dtype=np.float64)

        # Vectorized internal edge current
        jx_edges = self.coeff_x * (n_flat[self.vh] * bp_h - n_flat[self.uh] * bm_h)
        jx_a_m2.flat[self.uh] = jx_edges

        jy_edges = self.coeff_y * (n_flat[self.vv] * bp_v - n_flat[self.uv] * bm_v)
        jy_a_m2.flat[self.uv] = jy_edges

        # Terminal currents [A/um]
        i_source = - float(np.sum(jy_a_m2[0, :])) * self.dx * 1e-6
        i_drain = float(np.sum(jy_a_m2[-2, :])) * self.dx * 1e-6
        denom = max(abs(i_source), abs(i_drain), 1e-30)
        rel_imbalance = abs(i_source + i_drain) / denom

        return n_m3, phi_n, jx_a_m2, jy_a_m2, {
            "source_A_per_um": i_source,
            "drain_A_per_um": i_drain,
            "current_balance_relative": rel_imbalance,
            "current_resolved": abs(i_drain) > 1e-12
        }
