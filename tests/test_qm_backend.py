"""Tests for the scqo QM backend (customized.scqo).

`_to_canonical` and catalog registration are pure (no instrument, no QUAM). The
probe-equivalence and device-round-trip tests load a QUAM machine (no hardware
connection) and are skipped if quam_config / qm is unavailable.
"""

import numpy as np
import pytest
import xarray as xr

from customized.scqo.backend import QMBackend


# --------------------------------------------------------------------------- pure

def _raw(sweep_dim: str, n_qubits: int = 2, n_sweep: int = 5) -> xr.Dataset:
    data = np.zeros((n_qubits, n_sweep))
    return xr.Dataset(
        {"I": (("qubit", sweep_dim), data), "Q": (("qubit", sweep_dim), data)},
        coords={"qubit": [f"q{i}" for i in range(n_qubits)], sweep_dim: np.arange(n_sweep)},
    )


class _FakeExp:
    def __init__(self, sweep_axes):
        self.sweep_axes = sweep_axes


def test_to_canonical_renames_ramsey_axis():
    raw = _raw("idle_time")
    out = QMBackend._to_canonical(raw, _FakeExp({"idle_time_ns": np.arange(5)}))
    assert "idle_time_ns" in out.dims and "idle_time" not in out.dims
    assert set(out.data_vars) == {"I", "Q"}


def test_to_canonical_renames_power_rabi_axis():
    raw = _raw("amp_prefactor")
    out = QMBackend._to_canonical(raw, _FakeExp({"amp_factor": np.arange(5)}))
    assert "amp_factor" in out.dims and "amp_prefactor" not in out.dims


def test_to_canonical_renames_resonator_spec_axis():
    raw = _raw("detuning")
    out = QMBackend._to_canonical(raw, _FakeExp({"detuning_hz": np.arange(5)}))
    assert "detuning_hz" in out.dims and "detuning" not in out.dims


def test_to_canonical_noop_when_names_match():
    raw = _raw("idle_time_ns")
    out = QMBackend._to_canonical(raw, _FakeExp({"idle_time_ns": np.arange(5)}))
    assert "idle_time_ns" in out.dims


def test_to_canonical_rejects_multi_axis():
    raw = _raw("idle_time").expand_dims({"prepared_state": [0, 1]})
    with pytest.raises(NotImplementedError):
        QMBackend._to_canonical(raw, _FakeExp({"a": np.arange(5), "b": np.arange(2)}))


def test_catalog_registers_qm_experiments():
    import customized.scqo  # noqa: F401  (side effect: register)
    from scqo import catalog

    names = {e["name"] for e in catalog()}
    assert {"ramsey", "power_rabi", "resonator_spectroscopy"} <= names


# ------------------------------------------------------------------ requires QUAM

quam_config = pytest.importorskip("quam_config")
pytest.importorskip("qm")


@pytest.fixture(scope="module")
def machine():
    return quam_config.Quam.load()


def test_probe_matches_direct_build(machine):
    """QMRamsey/QMPowerRabi.probe() must produce the same QUA program as calling the
    LCHQM build_program directly with the mapped kwargs (proves the param mapping)."""
    from qm import generate_qua_script

    def script(prog):  # drop the volatile "generated at <timestamp>" header line
        return "\n".join(ln for ln in generate_qua_script(prog, config).splitlines() if "generated at" not in ln)

    from customized.probes._lib import select_qubits
    from customized.probes.ramsey import probe as ramsey_probe
    from customized.probes.power_rabi import probe as power_rabi_probe
    from customized.probes.resonator_spectroscopy import probe as resonator_spec_probe
    from customized.scqo.experiments.ramsey import QMRamsey
    from customized.scqo.experiments.power_rabi import QMPowerRabi
    from customized.scqo.experiments.resonator_spectroscopy import QMResonatorSpectroscopy

    backend = QMBackend(machine)
    config = machine.generate_config()
    qubits_names = ["q4", "q5"]
    qubits = select_qubits(machine, qubits_names, multiplexed=True)

    # Ramsey
    r = QMRamsey(backend, QMRamsey.Parameters(qubits=qubits_names, num_averages=200))
    r.sweep_axes = r.define_sweep()
    r_prog, _ = r.probe()
    idle_cycles = np.maximum(1, np.round(r.sweep_axes["idle_time_ns"] / 4)).astype(int)
    r_direct, _ = ramsey_probe.build_program(
        machine, qubits, idle_times_cycles=idle_cycles,
        detuning_hz=int(r.params.frequency_detuning_hz), num_shots=200,
        reset_type="thermal", use_state_discrimination=False,
    )
    assert script(r_prog) == script(r_direct)

    # Power Rabi
    p = QMPowerRabi(backend, QMPowerRabi.Parameters(qubits=qubits_names, num_averages=200))
    p.sweep_axes = p.define_sweep()
    p_prog, _ = p.probe()
    p_direct, _ = power_rabi_probe.build_program(
        machine, qubits, amps=p.sweep_axes["amp_factor"], operation="x180",
        num_shots=200, reset_type="thermal", use_state_discrimination=False, drive_qubit=None,
    )
    assert script(p_prog) == script(p_direct)

    # Resonator spectroscopy
    rs = QMResonatorSpectroscopy(
        backend, QMResonatorSpectroscopy.Parameters(qubits=qubits_names, num_averages=200)
    )
    rs.sweep_axes = rs.define_sweep()
    rs_prog, _ = rs.probe()
    rs_direct, _ = resonator_spec_probe.build_program(
        machine, qubits, dfs=rs.sweep_axes["detuning_hz"], num_shots=200,
    )
    assert script(rs_prog) == script(rs_direct)


def test_device_view_roundtrip(machine):
    """Neutral get/set maps onto QUAM; drive_freq shifts both f_01 and xy.RF_frequency."""
    backend = QMBackend(machine)
    view = backend.device.qubit("q4")
    q = machine.qubits["q4"]

    r0, d0, p0 = view.readout_freq, view.drive_freq, view.pi_amp
    rf0 = float(q.xy.RF_frequency)
    res_has_f01 = hasattr(q.resonator, "f_01")
    res_f01_0 = q.resonator.f_01 if res_has_f01 else None  # may be None when uncalibrated
    try:
        view.readout_freq = r0 + 1e6
        assert view.readout_freq == pytest.approx(r0 + 1e6)
        assert float(q.resonator.RF_frequency) == pytest.approx(r0 + 1e6)
        if res_has_f01:  # readout_freq setter writes resonator.f_01 too (even if it was None)
            assert float(q.resonator.f_01) == pytest.approx(r0 + 1e6)

        view.drive_freq = d0 + 2e6
        assert view.drive_freq == pytest.approx(d0 + 2e6)
        assert float(q.f_01) == pytest.approx(d0 + 2e6)
        assert float(q.xy.RF_frequency) == pytest.approx(rf0 + 2e6)  # shifted by same delta

        view.pi_amp = 0.123
        assert view.pi_amp == pytest.approx(0.123)

        snap = backend.device.snapshot()
        assert set(snap["q4"]) == {"readout_freq", "drive_freq", "pi_amp"}
    finally:
        # Restore the in-memory state (never saved); keep the loaded machine pristine.
        view.readout_freq = r0
        if res_has_f01:
            q.resonator.f_01 = res_f01_0
        q.f_01 = d0
        q.xy.RF_frequency = rf0
        view.pi_amp = p0
