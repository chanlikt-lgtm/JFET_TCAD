"""Unit tests for Scharfetter-Gummel transport solver."""
import unittest
import numpy as np

from src.device import create_jfet_device
from src.transport import FastTransportSolver

class TestTransportSolver(unittest.TestCase):
    def test_current_conservation(self):
        grid = create_jfet_device(0.2, pillar_width_um=2.2, gate_gap_um=1.8, gate_depth_um=0.6)
        solver = FastTransportSolver(grid)

        psi = grid.yy_um * (1.0 / grid.height_um)
        n_m3, phi_n, jx, jy, metrics = solver.solve_step(psi, v_gate=0.0, v_drain=1.0)

        # Terminal current balance
        self.assertLess(metrics["current_balance_relative"], 1e-4)
        self.assertTrue(metrics["current_resolved"])
        self.assertTrue(np.all(np.isfinite(n_m3)))

if __name__ == "__main__":
    unittest.main()
