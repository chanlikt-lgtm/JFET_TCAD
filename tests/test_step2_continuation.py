"""Unit tests for CP06 planning, guards, physical proxy, and data gates.

These tests do not constitute an end-to-end semiconductor validation.
"""
from __future__ import annotations
import importlib.util
from pathlib import Path
import numpy as np
import pytest

SRC = Path(__file__).resolve().parents[1] / "step2_dibl_continuation.py"
spec = importlib.util.spec_from_file_location("step2_dibl", SRC)
mod = importlib.util.module_from_spec(spec)
import sys
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)


def test_bias_schedule_requires_zero_and_monotone():
    assert mod.read_biases("0,1,5,20,50,100,200")[-1] == 200.0
    for s in ("1,5,200", "0,5,1", "0,1,1", "0,-1", ""):
        with pytest.raises(ValueError):
            mod.read_biases(s)


def test_minimax_band_barrier_uses_lowest_bottleneck_connected_path():
    psi = np.array([[0., 0., 0.],
                    [-1., -8., -2.],
                    [-1., -8., -2.],
                    [5., 5., 5.]])
    active = np.ones_like(psi, dtype=bool)
    source = np.zeros_like(active); source[0, :] = True
    drain = np.zeros_like(active); drain[-1, :] = True
    x = np.array([.1, .2, .3]); y = np.arange(4.)
    d = mod.minimax_path_barrier(psi, active, source, drain, x, y)
    assert d["barrier_proxy_eV"] == pytest.approx(1.0)
    assert d["bottleneck_x_um"] == pytest.approx(.1)
    assert d["source_psi_V"] == 0.0


def test_no_fabricated_connected_path():
    psi = np.zeros((3, 3))
    active = np.ones_like(psi, dtype=bool); active[1] = False
    src = np.zeros_like(active); src[0] = True
    dr = np.zeros_like(active); dr[-1] = True
    with pytest.raises(ValueError, match="No active path"):
        mod.minimax_path_barrier(psi, active, src, dr,
                                 np.arange(3.), np.arange(3.))


def test_conservation_based_current_resolution():
    src = np.array([1., 1.]); dr = np.array([1., 1.])
    case = mod.current_resolution(-2e-6, 2e-6, src, dr, 1e-7, 1e-12)
    assert case["current_resolved"]
    assert case["terminal_balance_relative"] == pytest.approx(0)
    low = mod.current_resolution(-2e-15, 2e-15, src, dr, 1e-7, 1e-12)
    assert not low["current_resolved"]
    imbalanced = mod.current_resolution(-1.0e-6, 2.0e-6, src, dr, 1e-7, 1e-12)
    assert not imbalanced["current_resolved"]


def test_post_transport_residual_is_mandatory():
    metrics = dict(gummel_converged=True, independent_poisson_residual_V=1e-7,
                   independent_correction_V=1e-7, finite_positive_density=True,
                   current_resolved=True, terminal_balance_relative=1e-7,
                   local_continuity_relative=1e-7)
    assert mod.validate_stage_metrics(metrics, tol_v=1e-6, balance_tol=1e-5) == []
    metrics["independent_poisson_residual_V"] = 2e-5
    assert mod.validate_stage_metrics(metrics, tol_v=1e-6, balance_tol=1e-5)
    metrics["independent_poisson_residual_V"] = 1e-7
    metrics["terminal_balance_relative"] = 1e-3
    assert mod.validate_stage_metrics(metrics, tol_v=1e-6, balance_tol=1e-5)


def fake_stage(v):
    return mod.Stage(v, np.zeros((2, 2)), np.zeros((2, 2)), {},
                     {"VDS_V": v, "barrier_proxy_eV": 2.0 - v/100}, [])


def test_adaptive_refinement_does_not_use_failed_state():
    calls = []
    def solve(v, previous):
        calls.append((v, None if previous is None else previous.bias_v))
        if v == 5.0 and previous.bias_v < 2:
            raise mod.StageFailure("nonlinear step failed")
        return fake_stage(v)
    accepted, attempts, status = mod.execute_continuation([0., 1., 5.], solve,
                        lambda s: [], min_step=.1, max_refinements=5)
    assert status == "COMPLETE"
    assert [s.bias_v for s in accepted] == [0., 1., 3., 5.]
    assert calls[:3] == [(0., None), (1., 0.), (5., 1.)]
    assert calls[-1] == (5., 3.)
    assert len([a for a in attempts if not a["accepted"]]) == 1


def test_refinement_stops_when_initial_case_fails():
    def fail(v, last):
        raise mod.StageFailure("cannot establish equilibrium")
    accepted, attempts, status = mod.execute_continuation([0., 1.], fail, lambda _: [])
    assert status == "BLOCKED"
    assert accepted == []
    assert len(attempts) == 1


def test_summary_never_claims_paper_validation():
    stages = [fake_stage(0), fake_stage(200)]
    stages[1].metrics["current_resolved"] = True
    summary = mod.summarize(stages, [0.,200.], "COMPLETE", warnings=[], forced=False)
    assert summary["CP06_numerical_transport"] == "PASS"
    assert summary["CP06_paper_reproduction"] == "PENDING_INDEPENDENT_VALIDATION"
    summary2 = mod.summarize(stages, [0.,200.], "COMPLETE",
                              warnings=["old geometry"], forced=True)
    assert summary2["CP06_numerical_transport"] != "PASS"


def test_source_blocker_detection(tmp_path):
    (tmp_path / "src").mkdir()
    (tmp_path / "src/gummel.py").write_text("max_cell_e_mv_cm * 1.15")
    (tmp_path / "src/device.py").write_text("gate_y0_um + gate_y1_um")
    (tmp_path / "src/poisson.py").write_text("-70.0, 30.0")
    assert len(mod.foundation_warnings(tmp_path)) == 3


def test_conservative_face_uniform_current_has_zero_free_divergence():
    class Grid:
        ny = 5; nx = 4
        dx_um = .1; dy_um = .1
        active_mask = np.ones((5, 4), dtype=bool)
        source_mask = np.zeros((5, 4), dtype=bool)
        drain_mask = np.zeros((5, 4), dtype=bool)
    grid = Grid()
    grid.source_mask[0] = True
    grid.drain_mask[-1] = True
    jx = np.zeros((5, 4))
    jy = np.full((5, 4), 8.2)   # directed down, last row unused
    jy[-1] = 0.0
    assert mod.local_continuity_norm(grid, jx, jy) == pytest.approx(0)
    assert mod.local_continuity_diagnostics(grid, jx, jy)["local_continuity_relative"] == pytest.approx(0)
    jy[2,1] *= 2
    assert mod.local_continuity_diagnostics(grid, jx, jy)["local_continuity_relative"] > 0.1


def test_export_schema_with_synthetic_stage(tmp_path):
    stage = fake_stage(0.0)
    stage.fields.update(x_um=np.array([0., 1.]), psi_V=np.zeros((2, 2)))
    stage.history.append({"iteration": 1, "poisson_residual_inf_V": "1e-8"})
    stage.metrics["current_resolved"] = False
    summary = mod.summarize([stage], [0, 1, 5], "BLOCKED", warnings=[], forced=False)
    mod.export_results(tmp_path, [stage], [{"VDS_V": 0., "accepted": True}],
                       summary, {"source_sha256": {"src/example.py": "abc"}},
                       save_fields="all")
    import json
    manifest = json.loads((tmp_path / "CP06_summary.json").read_text())
    assert manifest["continuation_status"] == "BLOCKED"
    assert manifest["CP06_numerical_transport"] == "NOT_ESTABLISHED"
    assert manifest["provenance"]["source_sha256"]
    assert (tmp_path / "CP06_VDS_0V_fields.npz").exists()
    assert (tmp_path / "CP06_VDS_0V_history.csv").exists()
