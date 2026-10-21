"""Unit tests for DeviceGrid and geometry creation."""
import unittest
import numpy as np

from src.device import create_jfet_device

class TestDeviceGeometry(unittest.TestCase):
    def test_grid_creation_and_symmetry(self):
        grid = create_jfet_device(mesh_spacing_um=0.2, pillar_width_um=2.2, gate_gap_um=1.8, gate_depth_um=0.6)
        
        # Check masks consistency
        self.assertEqual(grid.gate_mask.shape, grid.active_mask.shape)
        self.assertFalse(np.any(grid.gate_mask & grid.active_mask))
        self.assertEqual(int(grid.active_mask.sum()) + int(grid.gate_mask.sum()), grid.nx * grid.ny)
        
        # Check mirror symmetry
        asymmetry = np.count_nonzero(grid.gate_mask != grid.gate_mask[:, ::-1])
        self.assertEqual(asymmetry, 0, "Gate mask must be perfectly symmetric")

    def test_coarse_fine_matching(self):
        coarse = create_jfet_device(0.2, pillar_width_um=2.2, gate_gap_um=1.8, gate_depth_um=0.6)
        fine = create_jfet_device(0.1, pillar_width_um=2.2, gate_gap_um=1.8, gate_depth_um=0.6)
        
        self.assertAlmostEqual(coarse.gate_depth_um, fine.gate_depth_um, places=5)
        self.assertAlmostEqual(coarse.gate_gap_um, fine.gate_gap_um, places=5)

if __name__ == "__main__":
    unittest.main()
