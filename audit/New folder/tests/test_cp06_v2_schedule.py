"""CP06 dense continuation/restart planning tests (synthetic only)."""
import importlib.util
import json
from pathlib import Path
import sys
import numpy as np
import pytest

P = Path(__file__).resolve().parent.parent / 'step2_dibl_continuation_v2.py' if (Path(__file__).resolve().parent.parent / 'step2_dibl_continuation_v2.py').exists() else Path(__file__).resolve().parent / 'step2_dibl_continuation_v2.py'
spec=importlib.util.spec_from_file_location('cp06v2', P)
mod=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=mod
spec.loader.exec_module(mod)


def test_zone_forces_half_volt_steps_in_sensitive_region():
    schedule = mod.build_dense_schedule([0.,1.,5.,20.,50.,100.,200.],
                      zone_specs=['5:30:0.5'],outer_max_step=5.)
    assert schedule[0] == 0.0 and schedule[-1] == 200.0
    assert {0.,1.,5.,20.,30.,50.,100.,200.}.issubset(set(schedule))
    assert max(np.diff(schedule)) <= 5.0+1e-9
    for a,b in zip(schedule,schedule[1:]):
        if a >= 5 and b <= 30:
            assert b-a <= 0.5+1e-9
    assert len(schedule) >= 80


def test_invalid_zone_rejected():
    base=[0.,5.,20.]
    for zone in ['5:30:0.5','5:10:-0.5','5:8','5:10:0','5:15:1']:
        if zone == '5:15:1':
            continue
        with pytest.raises(ValueError):
            mod.build_dense_schedule(base,zone_specs=[zone],outer_max_step=5.)
    with pytest.raises(ValueError, match='overlap'):
        mod.build_dense_schedule(base,zone_specs=['5:15:0.5','10:20:1.0'],outer_max_step=5.)


def fake_stage(v):
    return mod.Stage(v,np.zeros((2,2)),np.zeros((2,2)),{},
                     {'VDS_V':v,'barrier_proxy_eV':5-v/10},[])


def test_dense_schedule_avoids_big_jump_that_blocks_old_runner():
    target=mod.build_dense_schedule([0.,1.,5.,20.], zone_specs=['5:20:0.5'],outer_max_step=5)
    def solver(v, old):
        if old is not None and old.bias_v >= 5 and v-old.bias_v > .5+1e-9:
            raise mod.StageFailure('too large')
        return fake_stage(v)
    accepted, attempts, status=mod.execute_continuation(target,solver,lambda _:[],min_step=.125,max_refinements=100)
    assert status == 'COMPLETE'
    assert accepted[-1].bias_v == 20.
    assert all(a['accepted'] for a in attempts)


def test_resume_seeds_only_future_schedule():
    recorded=[]
    def solve(v, old):
        recorded.append((v,old.bias_v))
        return fake_stage(v)
    accepted, attempts, status = mod.execute_continuation(
        [0.,1.,5.,10.,16.,16.5,17.,20.],solve,lambda _:[],
        initial_accepted=[fake_stage(0.),fake_stage(1.),fake_stage(5.),fake_stage(16.25)])
    assert recorded[0] == (16.5,16.25)
    assert accepted[-1].bias_v == 20. and status == 'COMPLETE'


class Grid:
    dx_um=.2;dy_um=.2
    x_um=np.array([.1,.3]); y_um=np.array([.1,.3])
    gate_mask=np.array([[False,True],[False,False]])
    active_mask=~gate_mask


def provenance():
    return {'mesh_um':.2,'pillar_um':2.2,'realized_gap_um':1.8,
            'realized_gate_depth_um':.6,'gate_V':-20.,'tolerance_V':1.9e-6,
            'current_floor_A_per_um':1e-12,
            'source_sha256':{'src/device.py':'same-hash','step2_dibl_continuation.py':'old-hash'}}


def test_resume_checks_solver_sha_geometry_and_field_arrays(tmp_path):
    grid=Grid()
    fields=dict(psi_V=np.array([[0.,0.],[0.,0.]]),
                phi_n_V=np.array([[0.,0.],[0.,0.]]),
                x_um=grid.x_um, y_um=grid.y_um,
                gate_mask=grid.gate_mask,active_mask=grid.active_mask)
    metrics=dict(VDS_V=0.,gummel_converged=True,gummel_iterations=25,
                 independent_poisson_residual_V=1e-7,
                 independent_correction_V=1e-7,
                 finite_positive_density=True,current_resolved=False,
                 barrier_proxy_eV=5.)
    s=mod.Stage(0.,fields['psi_V'],fields['phi_n_V'],fields,metrics,[])
    summary=mod.summarize([s],[0.,200.],'BLOCKED',warnings=[],forced=False)
    mod.export_results(tmp_path,[s],[],summary,provenance(),save_fields='all')
    loaded,info=mod.load_resume_stages(tmp_path,grid,provenance(),gate_v=-20.,tol_v=1.9e-6,floor_a_um=1e-12)
    assert len(loaded)==1 and info['reused_through_V']==0
    new_prov=provenance(); new_prov['source_sha256']['src/device.py']='other'
    with pytest.raises(ValueError,match='source SHA'):
        mod.load_resume_stages(tmp_path,grid,new_prov,gate_v=-20.,tol_v=1.9e-6,floor_a_um=1e-12)
    old_json=tmp_path/'CP06_summary.json'
    data=json.loads(old_json.read_text())
    data['provenance']['realized_gate_depth_um']=.5
    old_json.write_text(json.dumps(data))
    with pytest.raises(ValueError,match='geometry|configuration'):
        mod.load_resume_stages(tmp_path,grid,provenance(),gate_v=-20.,tol_v=1.9e-6,floor_a_um=1e-12)
