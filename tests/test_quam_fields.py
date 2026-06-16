"""Unit tests for the single neutral-field <-> QUAM mapping (customized.quam_fields).

Pure attribute access on a stub qubit -- no qm/quam needed. The existing
``test_*_update.py`` files exercise the same primitives through each node's
``apply_update`` (which now delegates here), so behaviour stays pinned on both sides.
"""

from types import SimpleNamespace

import pytest

from customized import quam_fields


def _qubit(*, f_01=5.0e9, xy_rf=5.1e9, res_rf=6.0e9, res_f01=6.0e9):
    return SimpleNamespace(
        f_01=f_01,
        xy=SimpleNamespace(
            RF_frequency=xy_rf,
            operations={"x180": SimpleNamespace(amplitude=0.2), "x90": SimpleNamespace(amplitude=0.1)},
        ),
        resonator=SimpleNamespace(RF_frequency=res_rf, f_01=res_f01),
    )


# ------------------------------------------------------------------- readout / resonator
def test_set_readout_freq_writes_rf_and_resonator_f01():
    q = _qubit()
    quam_fields.set_readout_freq(q, 6.5e9)
    assert q.resonator.RF_frequency == pytest.approx(6.5e9)
    assert q.resonator.f_01 == pytest.approx(6.5e9)


def test_set_readout_freq_skips_f01_when_absent():
    q = _qubit()
    q.resonator = SimpleNamespace(RF_frequency=6.0e9)  # no f_01 attribute
    quam_fields.set_readout_freq(q, 6.5e9)
    assert q.resonator.RF_frequency == pytest.approx(6.5e9)
    assert not hasattr(q.resonator, "f_01")


def test_shift_readout_freq_only_touches_rf():
    q = _qubit()
    quam_fields.shift_readout_freq(q, 250_000.0)
    assert q.resonator.RF_frequency == pytest.approx(6.0e9 + 250_000.0)
    assert q.resonator.f_01 == pytest.approx(6.0e9)  # untouched
    assert isinstance(q.resonator.RF_frequency, float)


# --------------------------------------------------------------------------- drive (f_01)
def test_set_drive_freq_preserves_f01_rf_offset():
    q = _qubit(f_01=5.0e9, xy_rf=5.1e9)  # offset = +100 MHz
    quam_fields.set_drive_freq(q, 5.002e9)
    assert q.f_01 == pytest.approx(5.002e9)
    assert q.xy.RF_frequency == pytest.approx(5.102e9)  # shifted by the same +2 MHz


def test_shift_drive_freq_moves_both_by_delta():
    q = _qubit(f_01=5.0e9, xy_rf=5.1e9)
    quam_fields.shift_drive_freq(q, -500_000.0)
    assert q.f_01 == pytest.approx(5.0e9 - 500_000.0)
    assert q.xy.RF_frequency == pytest.approx(5.1e9 - 500_000.0)


def test_drive_freq_seeds_f01_from_rf_when_unset():
    q = _qubit(f_01=None, xy_rf=5.1e9)
    quam_fields.shift_drive_freq(q, -1e6)
    # f_01 seeded from the drive RF (on resonance), then both shifted by -1 MHz
    assert q.f_01 == pytest.approx(5.1e9 - 1e6)
    assert q.xy.RF_frequency == pytest.approx(5.1e9 - 1e6)


# ------------------------------------------------------------------------------ pi amplitude
def test_set_pi_amp_locks_x90_for_x180():
    q = _qubit()
    quam_fields.set_pi_amp(q, 0.24, lock_x90=True)
    assert q.xy.operations["x180"].amplitude == pytest.approx(0.24)
    assert q.xy.operations["x90"].amplitude == pytest.approx(0.12)


def test_set_pi_amp_other_operation_never_touches_x90():
    q = _qubit()
    q.xy.operations["x90_DRAG"] = SimpleNamespace(amplitude=0.05)
    quam_fields.set_pi_amp(q, 0.06, operation="x90_DRAG", lock_x90=True)
    assert q.xy.operations["x90_DRAG"].amplitude == pytest.approx(0.06)
    assert q.xy.operations["x90"].amplitude == pytest.approx(0.1)  # untouched


def test_qmqubitview_uses_the_shared_mapping():
    """The scqo QMQubitView and quam_fields produce identical QUAM writes (the dedup)."""
    from customized.scqo.backend import QMQubitView

    q = _qubit(f_01=5.0e9, xy_rf=5.1e9)
    q.name = "q0"
    view = QMQubitView(q)

    view.drive_freq = 5.002e9
    assert q.f_01 == pytest.approx(5.002e9)
    assert q.xy.RF_frequency == pytest.approx(5.102e9)

    view.pi_amp = 0.3
    assert q.xy.operations["x180"].amplitude == pytest.approx(0.3)

    view.readout_freq = 6.4e9
    assert q.resonator.RF_frequency == pytest.approx(6.4e9)
    assert q.resonator.f_01 == pytest.approx(6.4e9)
