"""Unit tests for nonlinear 2D Poisson solver."""
import unittest
import numpy as np

from src.device import create_jfet_device
from src.poisson import FastPoissonSolver

class TestPoissonSolver(unittest.TestCase):
    def test_poisson_convergence(self):
        grid = create_jfet_device(0.2, pillar_width_um=2.2, gate_gap_um=1.8, gate_depth_um=0.6)
        solver = FastPoissonSolver(grid)

        phi_n = grid.yy_um * (1.0 / grid.height_um)
        psi = np.copy(phi_n)

        for _ in range(50):
            dpsi, dens, res, step = solver.solve_step(psi, phi_n, 0.0, 1.0)
            psi[grid.active_mask] += 0.8 * dpsi[grid.active_mask]
            if res < 1e-4:
                break

        self.assertLess(res, 1e-3)
        self.assertTrue(np.all(np.isfinite(psi)))
        self.assertTrue(np.all(dens[grid.active_mask] > 0))

if __name__ == "__main__":
    unittest.main()
