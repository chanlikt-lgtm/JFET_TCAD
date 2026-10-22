"""Device geometry, mesh generation, and doping profile definitions for 4H-SiC JFET.

Models the 4H-SiC vertical trench JFET defined in Monaghan et al. (KEM 948, 2023).
Features:
- Parameterized pillar width (nominal 2.4 um, variations 2.2 um, 2.3 um)
- Trench depth and P+ gate implant region (0.5 um depth, 1.77-1.80 um neck opening)
- 11 um drift epilayer (Nd = 4e15 cm^-3)
- Fully symmetric 2D grid generation ensuring zero mirror-asymmetry artifacts
- Support for both uniform equipotential gate electrodes and continuous P+/N doping
"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Optional
import numpy as np

from src.constants import (
    ND_DRIFT_CM3, NA_GATE_PEAK_CM3, ND_SOURCE_CM3, ND_DRAIN_CM3,
    W_PILLAR_NOMINAL_UM, H_DRIFT_UM, H_TOTAL_UM
)

@dataclass
class DeviceGrid:
    """2D structured Cartesian mesh and device structure."""
    nx: int
    ny: int
    dx_um: float
    dy_um: float
    x_um: np.ndarray       # 1D array of x coordinates [um]
    y_um: np.ndarray       # 1D array of y coordinates [um]
    xx_um: np.ndarray      # 2D coordinate meshgrid [um]
    yy_um: np.ndarray      # 2D coordinate meshgrid [um]
    
    # Masks
    gate_mask: np.ndarray    # True inside gate contact/electrode regions
    active_mask: np.ndarray  # True where Poisson & transport are solved
    source_mask: np.ndarray  # True on source contact boundary
    drain_mask: np.ndarray   # True on drain contact boundary
    
    # Net doping profile [cm^-3]: positive = donor (N), negative = acceptor (P)
    net_doping_cm3: np.ndarray
    nd_cm3: np.ndarray
    na_cm3: np.ndarray
    
    # Device physical dimensions [um]
    width_um: float
    height_um: float
    gate_depth_um: float
    gate_gap_um: float


def create_jfet_device(
    mesh_spacing_um: float = 0.1,
    pillar_width_um: float = 2.4,
    gate_gap_um: float = 1.8,
    gate_depth_um: float = 0.6,
    gate_y0_um: float = 0.4,
    total_height_um: float = 13.0,
    nd_drift_cm3: float = 4.0e15,
    na_gate_cm3: float = 1.0e19,
    mode: str = "equipotential_gate"
) -> DeviceGrid:
    """Create a strictly symmetric 2D trench JFET mesh and structure.

    Parameters
    ----------
    mesh_spacing_um : float
        Grid spacing dx = dy in micrometers (e.g. 0.1 for fine, 0.2 for coarse).
    pillar_width_um : float
        Pillar width in micrometers (default 2.4 um).
    gate_gap_um : float
        Channel gap between gate regions in micrometers (default 1.8 um).
    gate_depth_um : float
        Vertical depth of gate region in micrometers (default 0.6 um, compatible with 0.1/0.2 grids).
    gate_y0_um : float
        Top coordinate of gate region in micrometers.
    total_height_um : float
        Total device length in micrometers (default 13.0 um, containing 11 um drift).
    nd_drift_cm3 : float
        Drift region donor doping concentration in cm^-3.
    na_gate_cm3 : float
        Gate region acceptor doping concentration in cm^-3.
    mode : str
        'equipotential_gate' (gate cells excluded from active solve, held at Vg)
        or 'bipolar_full' (continuous P+/N junction throughout domain).
    """
    dx = float(mesh_spacing_um)
    dy = float(mesh_spacing_um)

    # Standard finite-volume cell-centered Cartesian mesh
    nx = int(round(pillar_width_um / dx))
    ny = int(round(total_height_um / dy))

    x_um = (np.arange(nx) + 0.5) * dx
    y_um = (np.arange(ny) + 0.5) * dy
    xx, yy = np.meshgrid(x_um, y_um)

    # Cell-aligned symmetric gate definition
    gate_wing_width = (pillar_width_um - gate_gap_um) / 2.0
    m_gate_x = int(round(gate_wing_width / dx))
    m_gate_y_start = int(round(gate_y0_um / dy))
    m_gate_y_count = int(round(gate_depth_um / dy))

    gate_mask = np.zeros((ny, nx), dtype=bool)
    if mode == "equipotential_gate" and m_gate_x > 0:
        gate_mask[m_gate_y_start:m_gate_y_start + m_gate_y_count, :m_gate_x] = True
        gate_mask[m_gate_y_start:m_gate_y_start + m_gate_y_count, -m_gate_x:] = True

    # Guarantee perfect mirror symmetry
    gate_mask = gate_mask | gate_mask[:, ::-1]

    # Active computational region
    active_mask = ~gate_mask

    # Boundary contact masks
    source_mask = np.zeros((ny, nx), dtype=bool)
    source_mask[0, :] = active_mask[0, :]

    drain_mask = np.zeros((ny, nx), dtype=bool)
    drain_mask[-1, :] = active_mask[-1, :]

    # Doping concentrations
    nd = np.full((ny, nx), nd_drift_cm3, dtype=np.float64)
    na = np.zeros((ny, nx), dtype=np.float64)

    # Source and drain heavy N+ contacts
    nd[0, :] = ND_SOURCE_CM3
    nd[-1, :] = ND_DRAIN_CM3

    # Gate P+ doping
    gate_y1_um = gate_y0_um + gate_depth_um
    if mode == "bipolar_full":
        # Realistic Monte Carlo / Gaussian lateral straggle
        p_dist_left = np.maximum(0.0, xx - gate_wing_width)
        p_dist_right = np.maximum(0.0, (pillar_width_um - gate_wing_width) - xx)
        y_gate_center = 0.5 * (gate_y0_um + gate_y1_um)
        sig_y = 0.5 * max(gate_depth_um, 1e-6)
        sig_x = 0.15  # lateral encroachment straggle ~ 0.15 um
        p_prof_left = na_gate_cm3 * np.exp(-((yy - y_gate_center) / sig_y)**2) * (xx <= gate_wing_width + 0.3)
        p_prof_right = na_gate_cm3 * np.exp(-((yy - y_gate_center) / sig_y)**2) * (xx >= pillar_width_um - gate_wing_width - 0.3)
        na = np.maximum(na, p_prof_left + p_prof_right)
    else:
        # Equipotential gate model
        na[gate_mask] = na_gate_cm3

    net_doping = nd - na

    # Actual realized dimensions on discrete mesh
    gate_rows = np.flatnonzero(gate_mask.any(axis=1))
    realized_depth = float(len(gate_rows) * dy) if gate_rows.size else 0.0
    realized_gap = float(active_mask[gate_rows].sum(axis=1).min() * dx) if gate_rows.size else pillar_width_um

    return DeviceGrid(
        nx=nx,
        ny=ny,
        dx_um=dx,
        dy_um=dy,
        x_um=x_um,
        y_um=y_um,
        xx_um=xx,
        yy_um=yy,
        gate_mask=gate_mask,
        active_mask=active_mask,
        source_mask=source_mask,
        drain_mask=drain_mask,
        net_doping_cm3=net_doping,
        nd_cm3=nd,
        na_cm3=na,
        width_um=pillar_width_um,
        height_um=total_height_um,
        gate_depth_um=realized_depth,
        gate_gap_um=realized_gap
    )
