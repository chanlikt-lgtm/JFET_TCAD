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

    def test_bipolar_full_mode(self):
        """IMP-07 / CP06: Ensure bipolar_full mode creates continuous P+/N doping without NameError."""
        grid_coarse = create_jfet_device(0.2, pillar_width_um=2.4, gate_gap_um=1.8, gate_depth_um=0.6, mode="bipolar_full")
        grid_fine = create_jfet_device(0.1, pillar_width_um=2.4, gate_gap_um=1.8, gate_depth_um=0.6, mode="bipolar_full")
        
        # Verify no NaN or nonfinite doping
        self.assertTrue(np.all(np.isfinite(grid_coarse.net_doping_cm3)))
        self.assertTrue(np.all(np.isfinite(grid_fine.net_doping_cm3)))
        
        # Verify P+ peak and N+ contacts
        self.assertLess(grid_coarse.net_doping_cm3.min(), -1e18, "P+ gate region must have negative net doping")
        self.assertGreater(grid_coarse.net_doping_cm3.max(), 1e19, "N+ contacts must have high donor doping")

    def test_unit_conversions(self):
        """IMP-10 / CP09: Verify physical unit conversion consistency."""
        from src.constants import V_UM_TO_MV_CM, calc_built_in_potential, NA_GATE_PEAK_CM3, ND_DRIFT_CM3
        # 1 V/um = 10^4 V/cm = 0.01 MV/cm
        self.assertAlmostEqual(1.0 * V_UM_TO_MV_CM, 0.01)
        # Built-in potential for 1e19 P+ and 4e15 N- in 4H-SiC is ~3.02 V
        vbi = calc_built_in_potential(NA_GATE_PEAK_CM3, ND_DRIFT_CM3)
        self.assertGreater(vbi, 2.9)
        self.assertLess(vbi, 3.2)

if __name__ == "__main__":
    unittest.main()
