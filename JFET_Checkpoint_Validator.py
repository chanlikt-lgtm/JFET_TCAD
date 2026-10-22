#!/usr/bin/env python3
"""Read-only checkpoint validator for the supplied KEM-948 reduced JFET simulation.

Checks the original archive manifest (optional), exported cases, nonlinear
stopping criteria, geometry symmetry, and the known paper-reproduction blocker.
It never edits the simulation files. It does not assert physical TCAD agreement.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

import numpy as np

CASES = ("paper_bias_approximation", "on_state_control")
ARTEFACT_SUFFIXES = ("metrics.json", "convergence.csv", "fields.npz", "centerline.csv",
                     "maps.png", "maps.pdf", "convergence.png", "convergence.pdf")


def checkpoint(results, name, status, detail):
    results.append({"checkpoint": name, "status": status, "detail": detail})
    print(f"[{status:9s}] {name}: {detail}", flush=True)


def check_manifest(root):
    manifest_path = root / "kem948_fig5_report" / "manifest.json"
    if not manifest_path.is_file():
        return False, "Manifest absent"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    items = manifest.get("files", [])
    failures = []
    for item in items:
        path = root / item["path"]
        if not path.is_file() or path.stat().st_size != item["bytes"]:
            failures.append(item["path"])
        elif hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
            failures.append(item["path"])
    return not failures, f"{len(items) - len(failures)}/{len(items)} hashes verified" + (
        "; mismatches: " + ", ".join(failures[:5]) if failures else "")


def read_case(folder: Path, label: str):
    missing = [f"{label}_{suffix}" for suffix in ARTEFACT_SUFFIXES
               if not (folder / f"{label}_{suffix}").is_file()]
    if missing:
        return None, "Missing files: " + ", ".join(missing)
    metrics = json.loads((folder / f"{label}_metrics.json").read_text(encoding="utf-8"))
    with (folder / f"{label}_convergence.csv").open(newline="", encoding="utf-8") as f:
        history = list(csv.DictReader(f))
    if not history:
        return None, "Empty convergence history"
    last = history[-1]
    if len(history) != int(metrics["iterations"]):
        return None, "Iteration CSV length does not match metrics"
    residual = float(last["poisson_residual_inf_V"])
    correction = float(last["undamped_correction_inf_V"])
    if not (np.isfinite(residual) and np.isfinite(correction) and
            residual < 2e-6 and correction < 2e-6):
        return None, f"Nonlinear convergence failed (residual={residual:g}, correction={correction:g})"
    if abs(residual - float(metrics["integrated_poisson_residual_V"])) > 1e-10:
        return None, "Final residual disagrees with metrics"
    if any(float(entry["accepted_step_inf_V"]) > 0.15 + 1e-12 for entry in history):
        return None, "Applied potential correction exceeded 0.15 V"
    expected = (-20.0, 200.0) if label == "paper_bias_approximation" else (0.0, 1.0)
    if (float(metrics["gate_v"]), float(metrics["drain_v"])) != expected:
        return None, f"Unexpected terminal biases: {metrics['gate_v']} V / {metrics['drain_v']} V"
    with np.load(folder / f"{label}_fields.npz") as fields:
        x, y = fields["x_um"], fields["y_um"]
        gate, active = fields["gate_mask"], fields["active_mask"]
        potential = fields["potential_v"]
        density = fields["density_cm3"]
        if (gate.shape != active.shape or gate.shape != potential.shape or
                np.any(gate & active) or int(active.sum()) != int(metrics["unknowns"])):
            return None, "Inconsistent masks or unknown count"
        if not (np.all(np.isfinite(potential[active])) and
                np.all(np.isfinite(density[active])) and np.all(density[active] > 0)):
            return None, "Nonfinite potential or invalid electron density"
        dx, dy = float(np.diff(x).mean()), float(np.diff(y).mean())
        gate_rows = np.flatnonzero(gate.any(axis=1))
        gate_depth = float(len(gate_rows) * dy)
        gate_gap = float(active[gate_rows].sum(axis=1).min() * dx) if gate_rows.size else None
        asymmetry = int(np.count_nonzero(gate != gate[:, ::-1]))
        mirror_potential = float(np.nanmax(np.abs(potential - potential[:, ::-1])))
    source, drain = float(metrics["source_A_per_um"]), float(metrics["drain_A_per_um"])
    relative_balance = abs(source + drain) / max(abs(source), abs(drain), 1e-30)
    if label == "on_state_control" and (not metrics["current_resolved"] or relative_balance >= 1e-5):
        return None, f"Resolved control current/conservation not passed: {relative_balance:g}"
    info = {
        "label": label, "mesh_dx_um": dx, "mesh_dy_um": dy,
        "iterations": int(metrics["iterations"]), "residual_V": residual,
        "correction_V": correction, "current_resolved": bool(metrics["current_resolved"]),
        "source_A_per_um": source, "drain_A_per_um": drain,
        "current_balance_relative": relative_balance if label == "on_state_control" else None,
        "gate_depth_um": gate_depth, "gate_gap_um": gate_gap,
        "contact_separation_um": float(y[-1] - y[0]),
        "mirror_gate_mismatch_cells": asymmetry,
        "mirror_potential_max_difference_V": mirror_potential,
        "max_cell_E_MV_cm": float(metrics["max_cell_E_MV_cm"]),
        "max_gate_face_E_MV_cm": float(metrics["max_gate_face_E_MV_cm"]),
        "center_barrier_eV": float(metrics["center_barrier_relative_bulk_eV"]),
    }
    return info, f"iterations={info['iterations']}; |r|={residual:.3g} V; current_resolved={info['current_resolved']}"


def run():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."),
                        help="Extracted directory containing simulate_kem948_fig5.py")
    parser.add_argument("--coarse", type=Path, default=Path("kem948_fig5_results/coarse"),
                        help="Coarse output directory, absolute or relative to root")
    parser.add_argument("--fine", type=Path, default=Path("kem948_fig5_results"),
                        help="Fine output directory, absolute or relative to root")
    parser.add_argument("--verify-manifest", action="store_true",
                        help="Verify as-received bundle payload hashes BEFORE rerunning/rebuilding")
    parser.add_argument("--run-self-test", action="store_true",
                        help="Run the original solver's built-in self-test (may take time)")
    parser.add_argument("--json", type=Path, help="Write a separate JSON summary")
    parser.add_argument("--scope", choices=["numerical", "scientific"], default="scientific",
                        help="Validation scope: 'numerical' passes basic convergence; 'scientific' (default) fail-stops on unvalidated/blocked physics")
    parser.add_argument("--strict", action="store_true",
                        help="Force fail-stop exit code 2 when geometric or physical-reproduction gates remain blocked")
    args = parser.parse_args()
    strict_mode = args.strict or (args.scope == "scientific")
    root = args.root.resolve()
    results, cases = [], {}
    source = root / "simulate_kem948_fig5.py"
    checkpoint(results, "CP00 - package", "PASS" if source.is_file() else "FAIL",
               str(source) if source.is_file() else "Missing simulate_kem948_fig5.py")
    if args.verify_manifest:
        try:
            ok, detail = check_manifest(root)
        except (KeyError, ValueError, OSError) as exc:
            ok, detail = False, repr(exc)
        checkpoint(results, "CP00a - manifest", "PASS" if ok else "FAIL", detail)
    else:
        checkpoint(results, "CP00a - manifest", "NOT RUN", "Use --verify-manifest on an untouched extraction")
    versions = {}
    for dep in ("numpy", "scipy", "matplotlib", "reportlab", "markdown-it-py"):
        try:
            versions[dep] = importlib.metadata.version(dep)
        except importlib.metadata.PackageNotFoundError:
            versions[dep] = "MISSING"
    env_text = f"Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}; " + ", ".join(f"{k}={v}" for k,v in versions.items())
    status = "PASS" if all(x != "MISSING" for x in versions.values()) else "FAIL"
    checkpoint(results, "CP01 - environment", status, env_text)
    if args.run_self_test and source.is_file():
        try:
            output = subprocess.run([sys.executable, str(source), "--self-test"], cwd=root,
                                    capture_output=True, text=True, timeout=600)
            obj = json.loads(output.stdout) if output.returncode == 0 else {}
            eq_flux = float(obj.get("equilibrium_flux_max_A_cm2", 1.0))
            ok = output.returncode == 0 and obj.get("equilibrium_flux_identity") == "PASS" \
                 and eq_flux < 1e-6 and obj.get("terminal_imbalance", 1) < 1e-5
            checkpoint(results, "CP02 - self-test", "PASS" if ok else "FAIL",
                       f"returncode={output.returncode}; max_eq_flux={eq_flux:.3e} A/cm2; " +
                       (f"relative balance={obj.get('terminal_imbalance')}" if ok else (output.stderr[-500:] or output.stdout[-500:])))
        except (subprocess.TimeoutExpired, json.JSONDecodeError) as exc:
            checkpoint(results, "CP02 - self-test", "FAIL", repr(exc))
    else:
        checkpoint(results, "CP02 - self-test", "NOT RUN", "Use --run-self-test after installing dependencies")
    def locate(path):
        return path if path.is_absolute() else root / path
    for mesh, folder in (("coarse", locate(args.coarse)), ("fine", locate(args.fine))):
        cases[mesh] = {}
        for label in CASES:
            try:
                info, detail = read_case(folder, label)
            except (OSError, KeyError, ValueError, IndexError, TypeError) as exc:
                info, detail = None, repr(exc)
            checkpoint(results, f"CP03/04 - {mesh} - {label}", "PASS" if info else "FAIL", detail)
            cases[mesh][label] = info
    same = [cases[m][label] for m in ("coarse", "fine") for label in CASES]
    if all(item is not None for item in same):
        coarse, fine = cases["coarse"][CASES[0]], cases["fine"][CASES[0]]
        symm = coarse["mirror_gate_mismatch_cells"] == 0 and fine["mirror_gate_mismatch_cells"] == 0
        identical = abs(coarse["gate_depth_um"] - fine["gate_depth_um"]) < 1e-9 \
            and abs(coarse["gate_gap_um"] - fine["gate_gap_um"]) < 1e-9
        status = "PASS" if symm and identical else "BLOCKED"
        checkpoint(results, "CP05 - geometry and mesh", status,
                   f"coarse/fine implant depth={coarse['gate_depth_um']:.3f}/{fine['gate_depth_um']:.3f} um; "
                   f"mismatched mirror cells={coarse['mirror_gate_mismatch_cells']}/{fine['mirror_gate_mismatch_cells']}. "
                   "This is NOT a 3-grid convergence certification.")
        nominal = cases["fine"][CASES[0]]
        checkpoint(results, "CP06 - paper DIBL comparison", "NOT VALIDATED" if not nominal["current_resolved"] else "REVIEW",
                   "Fine-grid nominal current is unresolved; paper Fig 5.1 conduction NOT reproduced" if not nominal["current_resolved"]
                   else "Resolved current alone does not establish source-drain DIBL; verify spatial paths/physics")
    else:
        checkpoint(results, "CP05 - geometry and mesh", "NOT RUN", "Generate/read both meshes first")
        checkpoint(results, "CP06 - paper DIBL comparison", "NOT RUN", "Nominal outputs unavailable")
    checkpoint(results, "CP07 - avalanche", "NOT AVAILABLE",
               "The supplied electron-only code does not implement impact-ionization or hole transport")
    summary = {"root": str(root), "checkpoints": results, "cases": cases,
               "scope": "Reduced-model numerical/integrity checks only; not a Sentaurus reproduction"}
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps(summary, indent=2), encoding="utf-8")
        print(f"Wrote JSON summary: {args.json}")
    failed = any(x["status"] == "FAIL" for x in results)
    blocked = any(x["status"] in ("BLOCKED", "NOT VALIDATED", "NOT AVAILABLE", "REVIEW") for x in results)
    
    if failed:
        print("\n[RESULT: FAIL-STOP] Critical numerical/integrity failure detected!")
    elif strict_mode and blocked:
        print("\n[RESULT: FAIL-STOP] Scientific validation gate BLOCKED (unresolved/unvalidated physics detected)!")
    else:
        print("\n[RESULT: PASS] All required checks passed under current scope.")
        
    print("Qualification: " + ("Numerical/integrity FAIL" if failed else "Numerical checks passed or skipped") +
          "; paper reproduction remains UNVALIDATED unless all physical gates are independently met")
    return 2 if failed or (strict_mode and blocked) else 0


if __name__ == "__main__":
    raise SystemExit(run())
