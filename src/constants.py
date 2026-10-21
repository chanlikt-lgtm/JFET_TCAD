"""Physical constants and 4H-SiC semiconductor material parameters.

All calculations support both SI units (m, s, kg, A, V) and standard TCAD units
(cm, V, A, s) with explicit conversion helpers.
"""
from dataclasses import dataclass

# Fundamental constants (CODATA 2018)
Q_E = 1.602176634e-19        # Elementary charge [C]
EPS_0 = 8.8541878128e-12     # Vacuum permittivity [F/m]
EPS_0_CM = 8.8541878128e-14  # Vacuum permittivity [F/cm]
K_B = 1.380649e-23           # Boltzmann constant [J/K]
T_ROOM = 300.0               # Standard simulation temperature [K]
V_T = K_B * T_ROOM / Q_E     # Thermal voltage ~ 0.025852 V

# 4H-SiC bulk material properties at 300 K
EPS_R_SIC = 9.7              # 4H-SiC static dielectric constant
EPS_SIC = EPS_R_SIC * EPS_0  # 4H-SiC permittivity [F/m]
EPS_SIC_CM = EPS_R_SIC * EPS_0_CM  # [F/cm]
E_G_SIC = 3.26               # Bandgap [eV]
N_I_SIC_CM3 = 8.2e-9         # Intrinsic carrier concentration [cm^-3]
N_I_SIC_M3 = N_I_SIC_CM3 * 1e6  # [m^-3]
N_C_SIC_CM3 = 1.7e19         # Effective conduction band DOS [cm^-3]
N_V_SIC_CM3 = 2.5e19         # Effective valence band DOS [cm^-3]

# Low-field carrier mobilities in 4H-SiC
MU_N0_CM2 = 800.0            # Electron low-field mobility [cm^2/(V*s)]
MU_N0_M2 = MU_N0_CM2 * 1e-4  # [m^2/(V*s)] = 0.08
MU_P0_CM2 = 115.0            # Hole low-field mobility [cm^2/(V*s)]
MU_P0_M2 = MU_P0_CM2 * 1e-4  # [m^2/(V*s)] = 0.0115

# Saturation velocities
V_SAT_N_CM = 2.0e7           # Electron saturation velocity [cm/s]
V_SAT_N_M = 2.0e5            # [m/s]
V_SAT_P_CM = 1.0e7           # Hole saturation velocity [cm/s]
V_SAT_P_M = 1.0e5            # [m/s]

# Carrier lifetimes for SRH recombination
TAU_N0 = 1.0e-7              # Electron lifetime [s]
TAU_P0 = 2.0e-8              # Hole lifetime [s]

# Okuto-Crowell / Chynoweth impact ionization parameters for 4H-SiC
# alpha = a * exp(-b / |E|) or a * |E| * exp(-b / |E|)
A_N_CM = 1.66e6              # Electron ionization prefactor [cm^-1]
B_N_V_CM = 1.27e7            # Electron ionization critical field [V/cm]
A_P_CM = 5.18e6              # Hole ionization prefactor [cm^-1]
B_P_V_CM = 1.55e7            # Hole ionization critical field [V/cm]
E_CRIT_SIC_V_CM = 3.0e6      # Nominal critical breakdown field [V/cm] = 3.0 MV/cm

# Default device parameters from Monaghan et al. (KEM 948, 2023)
ND_DRIFT_CM3 = 4.0e15        # Nominal drift epilayer doping [cm^-3]
ND_DRIFT_M3 = ND_DRIFT_CM3 * 1e6  # [m^-3]
NA_GATE_PEAK_CM3 = 1.0e19    # P+ gate implant peak doping [cm^-3]
ND_SOURCE_CM3 = 2.0e19       # N+ source contact doping [cm^-3]
ND_DRAIN_CM3 = 2.0e19        # N+ substrate drain doping [cm^-3]

W_PILLAR_NOMINAL_UM = 2.4    # Central pillar width [um]
W_TRENCH_UM = 1.0            # Trench width [um] on either side
H_TRENCH_UM = 0.5            # Trench depth [um]
H_DRIFT_UM = 11.0            # Drift layer thickness [um]
H_TOTAL_UM = 13.0            # Total simulated vertical extent [um]
TRENCH_BOTTOM_Y_UM = 2.0     # Trench recess top/bottom reference [um]

# Built-in potentials
PHI_BI_PN = V_T * 40.5       # ln(1e19 * 4e15 / ni^2) ~ 3.12 V
