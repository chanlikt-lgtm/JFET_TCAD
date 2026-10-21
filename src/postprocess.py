"""Post-processing, visualization, and artifact export for JFET TCAD simulations.

Generates:
1. 2D field contour maps (|J_n|, |E|, potential) in PNG and PDF formats
2. Convergence evolution histories (Poisson residual, undamped correction) in PNG and PDF
3. Centerline profile CSV
4. Metrics JSON conforming strictly to JFET_Checkpoint_Validator.py
5. Compressed fields NPZ archive containing all physical grid arrays
"""
from __future__ import annotations
import csv
import json
from pathlib import Path
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

def export_case_artifacts(
    output_dir: Path,
    label: str,
    metrics: dict,
    history: list[dict],
    field_data: dict,
    zoom_y_um: float = 6.0
) -> None:
    """Export all 8 standard artifacts for a given simulation case.

    Parameters
    ----------
    output_dir : Path
        Directory where artifacts are saved.
    label : str
        Prefix label: 'paper_bias_approximation', 'on_state_control', or 'user_bias'.
    metrics : dict
        Case summary metrics.
    history : list[dict]
        Per-iteration convergence records.
    field_data : dict
        Numpy arrays for coordinates, masks, potential, density, and fields.
    zoom_y_um : float
        Upper vertical limit [um] for 2D contour maps.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # 1. Export {label}_metrics.json
    metrics_path = output_dir / f"{label}_metrics.json"
    with open(metrics_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)

    # 2. Export {label}_convergence.csv
    csv_path = output_dir / f"{label}_convergence.csv"
    if history:
        keys = ["iteration", "poisson_residual_inf_V", "undamped_correction_inf_V", "accepted_step_inf_V"]
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            for row in history:
                writer.writerow(row)

    # 3. Export {label}_fields.npz
    npz_path = output_dir / f"{label}_fields.npz"
    np.savez_compressed(
        npz_path,
        x_um=field_data["x_um"],
        y_um=field_data["y_um"],
        gate_mask=field_data["gate_mask"],
        active_mask=field_data["active_mask"],
        potential_v=field_data["potential_v"],
        density_cm3=field_data["density_cm3"],
        ex_v_cm=field_data["ex_v_cm"],
        ey_v_cm=field_data["ey_v_cm"],
        jx_a_cm2=field_data["jx_a_cm2"],
        jy_a_cm2=field_data["jy_a_cm2"]
    )

    # 4. Export {label}_centerline.csv
    center_path = output_dir / f"{label}_centerline.csv"
    mid_col = len(field_data["x_um"]) // 2
    with open(center_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["y_um", "potential_v", "density_cm3", "e_mag_mv_cm", "jy_a_cm2"])
        e_mag = np.hypot(field_data["ex_v_cm"], field_data["ey_v_cm"]) / 1e6
        for j, y_val in enumerate(field_data["y_um"]):
            writer.writerow([
                f"{y_val:.4f}",
                f"{field_data['potential_v'][j, mid_col]:.6e}",
                f"{field_data['density_cm3'][j, mid_col]:.6e}",
                f"{e_mag[j, mid_col]:.6e}",
                f"{field_data['jy_a_cm2'][j, mid_col]:.6e}"
            ])

    # 5. Render {label}_maps.png and .pdf
    render_field_maps(output_dir, label, field_data, zoom_y_um)

    # 6. Render {label}_convergence.png and .pdf
    render_convergence_plots(output_dir, label, history)


def render_field_maps(output_dir: Path, label: str, field_data: dict, zoom_y_um: float = 6.0) -> None:
    """Render 3-panel 2D field contour maps side-by-side."""
    x = field_data["x_um"]
    y = field_data["y_um"]
    xx, yy = np.meshgrid(x, y)

    # Crop to upper zoom_y_um
    mask_y = y <= zoom_y_um
    y_crop = y[mask_y]
    xx_c = xx[mask_y, :]
    yy_c = yy[mask_y, :]

    pot_c = field_data["potential_v"][mask_y, :]
    gate_c = field_data["gate_mask"][mask_y, :]

    # Electric field magnitude [MV/cm]
    e_mag_c = np.hypot(field_data["ex_v_cm"][mask_y, :], field_data["ey_v_cm"][mask_y, :]) / 1e6

    # Current density magnitude [A/cm^2]
    j_mag_c = np.hypot(field_data["jx_a_cm2"][mask_y, :], field_data["jy_a_cm2"][mask_y, :])
    # Safe log current density
    j_log = np.log10(np.maximum(j_mag_c, 1e-12))

    fig, axes = plt.subplots(1, 3, figsize=(14, 6), sharey=True)

    # Panel 1: Current density |J|
    ax1 = axes[0]
    c1 = ax1.contourf(xx_c, yy_c, j_log, levels=40, cmap="viridis")
    ax1.contour(xx_c, yy_c, gate_c, levels=[0.5], colors="black", linewidths=1.5)
    fig.colorbar(c1, ax=ax1, label="log10(|J|) [A/cm²]")
    ax1.set_title("Current Density |J| (Fig 5.1/6.1)")
    ax1.set_xlabel("x [µm]")
    ax1.set_ylabel("y [µm]")
    ax1.invert_yaxis()

    # Panel 2: Electric field |E|
    ax2 = axes[1]
    c2 = ax2.contourf(xx_c, yy_c, e_mag_c, levels=40, cmap="plasma")
    ax2.contour(xx_c, yy_c, gate_c, levels=[0.5], colors="cyan", linewidths=1.5)
    fig.colorbar(c2, ax=ax2, label="|E| [MV/cm]")
    ax2.set_title("Electric Field |E| (Fig 5.2/6.2)")
    ax2.set_xlabel("x [µm]")

    # Panel 3: Potential psi
    ax3 = axes[2]
    c3 = ax3.contourf(xx_c, yy_c, pot_c, levels=40, cmap="inferno")
    ax3.contour(xx_c, yy_c, pot_c, levels=15, colors="white", alpha=0.4, linewidths=0.7)
    ax3.contour(xx_c, yy_c, gate_c, levels=[0.5], colors="white", linewidths=1.5)
    fig.colorbar(c3, ax=ax3, label="Potential [V]")
    ax3.set_title("Electrostatic Potential ψ [V]")
    ax3.set_xlabel("x [µm]")

    plt.tight_layout()
    fig.savefig(output_dir / f"{label}_maps.png", dpi=300)
    fig.savefig(output_dir / f"{label}_maps.pdf")
    plt.close(fig)


def render_convergence_plots(output_dir: Path, label: str, history: list[dict]) -> None:
    """Render convergence history plots."""
    if not history:
        return

    iters = [int(h["iteration"]) for h in history]
    res = [float(h["poisson_residual_inf_V"]) for h in history]
    corr = [float(h["undamped_correction_inf_V"]) for h in history]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    ax.semilogy(iters, res, label="Poisson Residual [V]", color="royalblue", lw=1.8)
    ax.semilogy(iters, corr, label="Undamped Correction [V]", color="crimson", lw=1.8, ls="--")
    ax.axhline(2e-6, color="forestgreen", ls=":", label="Tolerance (2e-6 V)")

    ax.set_xlabel("Iteration")
    ax.set_ylabel("Error Metric [V]")
    ax.set_title(f"Convergence History: {label}")
    ax.grid(True, which="both", ls="--", alpha=0.5)
    ax.legend()
    plt.tight_layout()

    fig.savefig(output_dir / f"{label}_convergence.png", dpi=300)
    fig.savefig(output_dir / f"{label}_convergence.pdf")
    plt.close(fig)
