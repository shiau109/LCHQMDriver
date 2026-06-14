"""Unit tests for the pure readout-frequency update decision
(customized.node.LCH_readout_frequency.update)."""

import math
from types import SimpleNamespace

import pytest

from customized.node.LCH_readout_frequency.update import (
    ReadoutFreqUpdate,
    apply_update,
    compute_update,
)


def test_compute_update_takes_best_detuning():
    upd = compute_update({"best_detuning": 250_000.0, "best_fidelity": 0.95, "success": True})
    assert upd.detuning == pytest.approx(250_000.0)


def test_compute_update_negative_detuning():
    upd = compute_update({"best_detuning": -1.2e6})
    assert upd.detuning == pytest.approx(-1.2e6)


def test_compute_update_nan_propagates():
    # A failed fit reports NaN; the shell gates on outcomes, but the pure
    # function must not mask the NaN into a silent zero-shift.
    upd = compute_update({"best_detuning": float("nan"), "success": False})
    assert math.isnan(upd.detuning)


class _FakeQubit:
    def __init__(self):
        self.resonator = SimpleNamespace(RF_frequency=6.0e9)


def test_apply_update_shifts_rf_frequency():
    q = _FakeQubit()
    apply_update(q, ReadoutFreqUpdate(detuning=250_000.0))
    assert q.resonator.RF_frequency == pytest.approx(6.0e9 + 250_000.0)
    assert isinstance(q.resonator.RF_frequency, float)
