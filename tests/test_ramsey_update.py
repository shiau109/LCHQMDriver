"""Unit tests for the pure Ramsey update decision (customized.node.LCH_Ramsey.update).

Frequencies in the fit metadata are in GHz (scqat convention); corrections in Hz.
"""

from types import SimpleNamespace

from customized.node.LCH_Ramsey.update import RamseyUpdate, apply_update, compute_update


def test_single_model():
    # 2.5 MHz fitted fringe with 2 MHz virtual detuning -> qubit is 0.5 MHz off
    upd = compute_update({"model_type": "single", "f_1": 2.5e-3}, detuning_hz=2_000_000)
    assert upd.d_f01 == 500_000
    assert upd.charge_dispersion == 0


def test_beat_model():
    # beat at 2.4 / 2.6 MHz -> mean 2.5 MHz calibrates, half-split 0.1 MHz is dispersion
    upd = compute_update({"model_type": "beat", "f_1": 2.4e-3, "f_2": 2.6e-3}, detuning_hz=2_000_000)
    assert upd.d_f01 == 500_000
    assert upd.charge_dispersion == 100_000


def test_relaxation_model():
    # unresolvable fringe reports f_1 = 0 -> correction is -detuning
    upd = compute_update({"model_type": "relaxation", "f_1": 0.0}, detuning_hz=2_000_000)
    assert upd.d_f01 == -2_000_000
    assert upd.charge_dispersion == 0


def test_missing_model_type_falls_back_to_single_path():
    upd = compute_update({"f_1": 1e-3}, detuning_hz=0)
    assert upd.d_f01 == 1_000_000
    assert upd.charge_dispersion == 0


class _FakeQubit:
    def __init__(self):
        self.f_01 = 5_000_000_000
        self.xy = SimpleNamespace(RF_frequency=5_100_000_000)
        self.charge_dispersion = 123


def test_apply_update_writes_all_three_fields():
    q = _FakeQubit()
    apply_update(q, RamseyUpdate(d_f01=500_000, charge_dispersion=42))
    assert q.f_01 == 5_000_000_000 - 500_000
    assert q.xy.RF_frequency == 5_100_000_000 - 500_000
    assert q.charge_dispersion == 42
