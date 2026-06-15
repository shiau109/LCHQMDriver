"""Unit tests for the pure power-Rabi update decision (customized.node.LCH_power_rabi.update)."""

from types import SimpleNamespace

import pytest

from customized.node.LCH_power_rabi.update import PowerRabiUpdate, apply_update, compute_update


def test_compute_update_scales_current_amplitude():
    upd = compute_update({"opt_amp_prefactor": 1.1, "success": True}, current_amplitude=0.2)
    assert upd.opt_amp == pytest.approx(0.22)


def test_compute_update_prefactor_below_one_reduces_amplitude():
    upd = compute_update({"opt_amp_prefactor": 0.5}, current_amplitude=0.2)
    assert upd.opt_amp == pytest.approx(0.1)


class _FakeQubit:
    def __init__(self):
        self.xy = SimpleNamespace(
            operations={
                "x180": SimpleNamespace(amplitude=0.2),
                "x90": SimpleNamespace(amplitude=0.123),
            }
        )


def test_apply_update_x180_with_x90_halving():
    q = _FakeQubit()
    apply_update(q, "x180", PowerRabiUpdate(opt_amp=0.24), update_x90=True)
    assert q.xy.operations["x180"].amplitude == pytest.approx(0.24)
    assert q.xy.operations["x90"].amplitude == pytest.approx(0.12)


def test_apply_update_x180_without_x90_update():
    q = _FakeQubit()
    apply_update(q, "x180", PowerRabiUpdate(opt_amp=0.24), update_x90=False)
    assert q.xy.operations["x180"].amplitude == pytest.approx(0.24)
    assert q.xy.operations["x90"].amplitude == pytest.approx(0.123)  # untouched


def test_apply_update_non_x180_never_touches_x90():
    q = _FakeQubit()
    q.xy.operations["x90_DRAG"] = SimpleNamespace(amplitude=0.05)
    apply_update(q, "x90_DRAG", PowerRabiUpdate(opt_amp=0.06), update_x90=True)
    assert q.xy.operations["x90_DRAG"].amplitude == pytest.approx(0.06)
    assert q.xy.operations["x90"].amplitude == pytest.approx(0.123)  # untouched
