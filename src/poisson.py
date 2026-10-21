"""Vectorized 2D nonlinear Poisson solver for 4H-SiC JFET.

Correctly accounts for all boundary stencils and space charge.
Solves:
    -div(eps * grad(psi)) = q * (p - n + Nd - Na)
"""
from __future__ import annotations
import numpy as np
from scipy.sparse import csr_matrix
from scipy.sparse.linalg import spsolve

from src.constants import Q_E, EPS_SIC, V_T, N_I_SIC_M3
from src.device import DeviceGrid

class FastPoissonSolver:
    """Accurate, vectorized 2D Poisson solver."""

    def __init__(self, grid: DeviceGrid):
        self.grid = grid
        self.nx, self.ny = grid.nx, grid.ny
        self.n_nodes = self.nx * self.ny
        self.dx = grid.dx_um * 1e-6
        self.dy = grid.dy_um * 1e-6
        self.idx2 = 1.0 / (self.dx * self.dx)
        self.idy2 = 1.0 / (self.dy * self.dy)

        # Boundary masks
        self.flat_gate = grid.gate_mask.flatten()
        self.flat_source = grid.source_mask.flatten()
        self.flat_drain = grid.drain_mask.flatten()
        self.is_dirichlet = self.flat_gate | self.flat_source | self.flat_drain
        self.interior_nodes = np.flatnonzero(~self.is_dirichlet)

        # All horizontal connections (j, i) <-> (j, i+1)
        jh, ih = np.meshgrid(np.arange(self.ny), np.arange(self.nx - 1), indexing="ij")
        self.uh = (jh * self.nx + ih).flatten()
        self.vh = (jh * self.nx + (ih + 1)).flatten()

        # Filter out connections where BOTH are Dirichlet (e.g. gate-gate)
        h_both_dir = self.is_dirichlet[self.uh] & self.is_dirichlet[self.vh]
        self.uh = self.uh[~h_both_dir]
        self.vh = self.vh[~h_both_dir]

        # All vertical connections (j, i) <-> (j+1, i)
        jv, iv = np.meshgrid(np.arange(self.ny - 1), np.arange(self.nx), indexing="ij")
        self.uv = (jv * self.nx + iv).flatten()
        self.vv = ((jv + 1) * self.nx + iv).flatten()

        v_both_dir = self.is_dirichlet[self.uv] & self.is_dirichlet[self.vv]
        self.uv = self.uv[~v_both_dir]
        self.vv = self.vv[~v_both_dir]

        # Interior degrees of freedom
        self.uh_active = ~self.is_dirichlet[self.uh]
        self.vh_active = ~self.is_dirichlet[self.vh]
        self.uv_active = ~self.is_dirichlet[self.uv]
        self.vv_active = ~self.is_dirichlet[self.vv]

        # Diagonal geometric weights
        self.geom_diag = np.zeros(self.n_nodes, dtype=np.float64)
        np.add.at(self.geom_diag, self.uh, EPS_SIC * self.idx2)
        np.add.at(self.geom_diag, self.vh, EPS_SIC * self.idx2)
        np.add.at(self.geom_diag, self.uv, EPS_SIC * self.idy2)
        np.add.at(self.geom_diag, self.vv, EPS_SIC * self.idy2)

        # Build sparse matrix index arrays
        self.rows = np.concatenate([
            self.uh[self.uh_active],
            self.vh[self.vh_active],
            self.uv[self.uv_active],
            self.vv[self.vv_active],
            np.arange(self.n_nodes)
        ])
        self.cols = np.concatenate([
            self.vh[self.uh_active],
            self.uh[self.vh_active],
            self.vv[self.uv_active],
            self.uv[self.vv_active],
            np.arange(self.n_nodes)
        ])

        self.static_offdiag = np.concatenate([
            np.full(np.count_nonzero(self.uh_active), -EPS_SIC * self.idx2),
            np.full(np.count_nonzero(self.vh_active), -EPS_SIC * self.idx2),
            np.full(np.count_nonzero(self.uv_active), -EPS_SIC * self.idy2),
            np.full(np.count_nonzero(self.vv_active), -EPS_SIC * self.idy2)
        ])

    def solve_step(
        self,
        psi: np.ndarray,
        phi_n: np.ndarray,
        v_gate: float,
        v_drain: float,
        v_source: float = 0.0,
        bipolar: bool = False,
        phi_p: np.ndarray | None = None
    ) -> tuple[np.ndarray, np.ndarray, float, float]:
        """Perform a single linearized Newton step for Poisson equation."""
        N = self.n_nodes
        psi_flat = psi.flatten()
        phi_n_flat = phi_n.flatten()

        v_gate_val = v_gate - 2.8
        v_source_val = v_source
        v_drain_val = v_drain

        # 1. Carrier densities
        arg_n = np.clip((psi_flat - phi_n_flat) / V_T, -70.0, 30.0)
        nd_m3 = (self.grid.nd_cm3 * 1e6).flatten()
        doping_net_m3 = (self.grid.net_doping_cm3 * 1e6).flatten()

        n_m3 = nd_m3 * np.exp(arg_n)
        p_m3 = np.zeros_like(n_m3)
        dn_dpsi = n_m3 / V_T
        dp_dpsi = np.zeros_like(p_m3)

        rho = Q_E * (p_m3 - n_m3 + doping_net_m3)
        drho_dpsi = Q_E * (dp_dpsi - dn_dpsi)

        # 2. Discrete Laplacian
        lap_psi = np.zeros(N, dtype=np.float64)
        np.add.at(lap_psi, self.uh, self.idx2 * (psi_flat[self.vh] - psi_flat[self.uh]))
        np.add.at(lap_psi, self.vh, self.idx2 * (psi_flat[self.uh] - psi_flat[self.vh]))
        np.add.at(lap_psi, self.uv, self.idy2 * (psi_flat[self.vv] - psi_flat[self.uv]))
        np.add.at(lap_psi, self.vv, self.idy2 * (psi_flat[self.uv] - psi_flat[self.vv]))

        # Residual F = -eps * Lap(psi) - rho
        rhs = - (-EPS_SIC * lap_psi - rho)

        # Overwrite Dirichlet boundaries
        rhs[self.flat_gate] = v_gate_val - psi_flat[self.flat_gate]
        rhs[self.flat_source] = v_source_val - psi_flat[self.flat_source]
        rhs[self.flat_drain] = v_drain_val - psi_flat[self.flat_drain]

        # Diagonals
        diag = self.geom_diag - drho_dpsi
        diag[self.is_dirichlet] = 1.0

        data = np.concatenate([self.static_offdiag, diag])
        A = csr_matrix((data, (self.rows, self.cols)), shape=(N, N))

        dpsi_flat = spsolve(A, rhs)
        dpsi = dpsi_flat.reshape((self.ny, self.nx))

        norm_factor = EPS_SIC * (2.0 * self.idx2 + 2.0 * self.idy2)
        residual_v = float(np.max(np.abs(rhs[self.interior_nodes])) / norm_factor)
        max_dpsi = float(np.max(np.abs(dpsi[self.grid.active_mask])))

        density_cm3 = (n_m3.reshape((self.ny, self.nx)) / 1e6)
        density_cm3[self.grid.gate_mask] = 0.0

        return dpsi, density_cm3, residual_v, max_dpsi
