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


def test_to_canonical_renames_two_axes():
    """2D sweeps (punchout): both axes rename positionally with size checks."""
    data = np.zeros((2, 5, 3))
    raw = xr.Dataset(
        {"I": (("qubit", "detuning", "power"), data), "Q": (("qubit", "detuning", "power"), data)},
        coords={"qubit": ["q0", "q1"], "detuning": np.arange(5), "power": np.arange(3)},
    )
    out = QMBackend._to_canonical(
        raw, _FakeExp({"detuning_hz": np.arange(5), "power_dbm": np.arange(3)})
    )
    assert {"detuning_hz", "power_dbm"} <= set(out.dims)
    assert out["I"].dims == ("target", "detuning_hz", "power_dbm")


def test_to_canonical_name_based_ignores_order_2d():
    """Flux spectroscopy: raw nesting (detuning_hz, flux_bias_v) vs scqo declaration
    (flux_bias_v, detuning_hz), with EQUAL sizes — positional renaming would swap the
    axes silently; the name-based path must leave the data untouched."""
    n = 4  # equal-length axes: the dangerous case
    data = np.arange(2 * n * n, dtype=float).reshape(2, n, n)
    raw = xr.Dataset(
        {"I": (("qubit", "detuning_hz", "flux_bias_v"), data), "Q": (("qubit", "detuning_hz", "flux_bias_v"), data)},
        coords={"qubit": ["q0", "q1"], "detuning_hz": np.linspace(-1e6, 1e6, n), "flux_bias_v": np.linspace(-0.1, 0.1, n)},
    )
    out = QMBackend._to_canonical(
        raw, _FakeExp({"flux_bias_v": np.zeros(n), "detuning_hz": np.zeros(n)})
    )
    assert out["I"].dims == ("target", "detuning_hz", "flux_bias_v")  # raw order kept
    np.testing.assert_array_equal(out["I"].values, data)
    np.testing.assert_array_equal(out["detuning_hz"].values, raw["detuning_hz"].values)


def test_to_canonical_name_based_single_shot():
    """Per-shot readout: raw nesting (shot_idx, prepared_state) vs scqo declaration
    (prepared_state, shot_idx) — resolved by name, sizes checked per name."""
    n_shots = 7
    data = np.zeros((2, n_shots, 2))
    raw = xr.Dataset(
        {"I": (("qubit", "shot_idx", "prepared_state"), data), "Q": (("qubit", "shot_idx", "prepared_state"), data)},
        coords={"qubit": ["q0", "q1"], "shot_idx": np.arange(1, n_shots + 1), "prepared_state": [0, 1]},
    )
    out = QMBackend._to_canonical(
        raw, _FakeExp({"prepared_state": np.array([0, 1]), "shot_idx": np.arange(n_shots)})
    )
    assert out["I"].dims == ("target", "shot_idx", "prepared_state")
    # size check is per NAME even though the declaration order differs
    bad = _FakeExp({"prepared_state": np.array([0, 1]), "shot_idx": np.arange(n_shots + 1)})
    with pytest.raises(ValueError):
        QMBackend._to_canonical(raw, bad)


def test_to_canonical_rejects_axis_count_mismatch():
    raw = _raw("idle_time")  # one sweep axis
    with pytest.raises(NotImplementedError):
        QMBackend._to_canonical(raw, _FakeExp({"a": np.arange(5), "b": np.arange(2)}))


def test_to_canonical_rejects_axis_size_mismatch():
    raw = _raw("idle_time", n_sweep=5)
    with pytest.raises(ValueError):
        QMBackend._to_canonical(raw, _FakeExp({"idle_time_ns": np.arange(7)}))


def test_catalog_registers_qm_experiments():
    import customized.scqo  # noqa: F401  (side effect: register)
    from scqo import catalog

    names = {e["name"] for e in catalog()}
    assert {"qubit_ramsey", "qubit_power_rabi", "resonator_spectroscopy"} <= names


# ------------------------------------------------------------------ requires QUAM

quam_config = pytest.importorskip("quam_config")
pytest.importorskip("qm")


@pytest.fixture(scope="module")
def machine():
    # my_quam.py's root class is toggled per experiment (FluxTunableQuam <->
    # FixedFrequencyQuam, see CLAUDE.md "Key Entrypoints"); the default-resolved
    # QUAM state may not match the currently toggled root (e.g. a flux-tunable
    # quam_state with qubit_pairs cannot validate under a FixedFrequencyQuam root).
    # That mismatch is a legitimate working-tree situation, not a test failure.
    try:
        return quam_config.Quam.load()
    except TypeError as err:
        pytest.skip(f"default QUAM state does not match the toggled my_quam root class: {err}")


def test_probe_matches_direct_build(machine):
    """QMQubitRamsey/QMQubitPowerRabi.probe() must produce the same QUA program as calling the
    LCHQM build_program directly with the mapped kwargs (proves the param mapping)."""
    from qm import generate_qua_script

    def script(prog):  # drop the volatile "generated at <timestamp>" header line
        return "\n".join(ln for ln in generate_qua_script(prog, config).splitlines() if "generated at" not in ln)

    from customized.probes._lib import select_qubits
    from customized.probes import qubit_ramsey as ramsey_probe
    from customized.probes import qubit_power_rabi as power_rabi_probe
    from customized.probes import resonator_spectroscopy as resonator_spec_probe
    from customized.scqo.experiments.qubit_ramsey import QMQubitRamsey
    from customized.scqo.experiments.qubit_power_rabi import QMQubitPowerRabi
    from customized.scqo.experiments.resonator_spectroscopy import QMResonatorSpectroscopy

    backend = QMBackend(machine)
    config = machine.generate_config()
    qubits_names = ["q4", "q5"]
    qubits = select_qubits(machine, qubits_names, multiplexed=True)

    # Ramsey
    r = QMQubitRamsey(backend, QMQubitRamsey.Parameters(targets=qubits_names, num_averages=200))
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
    p = QMQubitPowerRabi(backend, QMQubitPowerRabi.Parameters(targets=qubits_names, num_averages=200))
    p.sweep_axes = p.define_sweep()
    p_prog, _ = p.probe()
    p_direct, _ = power_rabi_probe.build_program(
        machine, qubits, amps=p.sweep_axes["amp_factor"], operation="x180",
        num_shots=200, reset_type="thermal", use_state_discrimination=False, drive_qubit=None,
    )
    assert script(p_prog) == script(p_direct)

    # Resonator spectroscopy
    rs = QMResonatorSpectroscopy(
        backend, QMResonatorSpectroscopy.Parameters(targets=qubits_names, num_averages=200)
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
    view = backend.device.component("q4")
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

        a0 = view.readout_amp
        view.readout_amp = 0.111
        assert view.readout_amp == pytest.approx(0.111)
        assert float(q.resonator.operations["readout"].amplitude) == pytest.approx(0.111)
        view.readout_amp = a0

        snap = backend.device.snapshot()
        assert set(snap["q4"]) == {"readout_freq", "drive_freq", "pi_amp", "drag_beta",
                                   "drive_amp", "drive_power_dbm",
                                   "readout_amp", "readout_power_dbm", "readout_duration_s",
                                   "readout_integration_s", "idle_flux_v"}
        # the pair entries carry the two coupler knobs (pull-mode seed source)
        for pair_name in backend.machine.qubit_pairs:
            assert set(snap[pair_name]) == {"coupler_decouple_v", "coupler_interaction_v"}

        # Window round-trip on the REAL QUAM pulse (reference semantics the stub
        # tests only mimic) — only from the default-weights form, restored after.
        pulse = q.resonator.operations["readout"]
        length_ns = int(pulse.length)
        if pulse.integration_weights == [(1, length_ns)]:
            view.readout_integration_s = (length_ns // 2 // 4 * 4) * 1e-9
            assert pulse.integration_weights[0][0] == 1.0
            assert view.readout_integration_s == pytest.approx(
                (length_ns // 2 // 4 * 4) * 1e-9)
            view.readout_integration_s = length_ns * 1e-9  # restore the reference form
            assert view.readout_integration_s == pytest.approx(length_ns * 1e-9)
    finally:
        # Restore the in-memory state (never saved); keep the loaded machine pristine.
        view.readout_freq = r0
        if res_has_f01:
            q.resonator.f_01 = res_f01_0
        q.f_01 = d0
        q.xy.RF_frequency = rf0
        view.pi_amp = p0


def test_readout_power_dbm_roundtrip(machine):
    """v0.8 absolute power: the setter re-solves (full_scale_power_dbm, amplitude) with
    the SMALLEST grid full-scale keeping amp <= 0.5 — bidirectional (a lower target
    lowers full scale again, unlike the bare power_tools helper)."""
    backend = QMBackend(machine)
    view = backend.device.component("q4")
    q = machine.qubits["q4"]
    fs0 = q.resonator.opx_output.full_scale_power_dbm
    amp0 = q.resonator.operations["readout"].amplitude
    try:
        # mid-range target: unclamped grid solve -> amp lands in (0.354, 0.5]
        view.readout_power_dbm = -2.0
        assert view.readout_power_dbm == pytest.approx(-2.0, abs=1e-6)
        assert q.resonator.opx_output.full_scale_power_dbm == 7  # smallest grid value >= -2+6.02
        amp = float(q.resonator.operations["readout"].amplitude)
        assert 0.354 < amp <= 0.5

        # low target: full scale goes back DOWN (grid floor -11), amp is the exact residual
        view.readout_power_dbm = -24.3
        assert view.readout_power_dbm == pytest.approx(-24.3, abs=1e-6)
        assert q.resonator.opx_output.full_scale_power_dbm == -11  # grid floor
        assert float(q.resonator.operations["readout"].amplitude) == pytest.approx(
            10 ** ((-24.3 + 11) / 20.0)
        )

        # ceiling: +10 dBm pins full scale at 16 and needs amp just above 0.5 -> warns
        with pytest.warns(UserWarning, match="canonical operating point"):
            view.readout_power_dbm = 10.0
        assert view.readout_power_dbm == pytest.approx(10.0, abs=1e-6)
        assert q.resonator.opx_output.full_scale_power_dbm == 16
    finally:
        q.resonator.opx_output.full_scale_power_dbm = fs0
        q.resonator.operations["readout"].amplitude = amp0


def test_readout_power_dbm_undefined_on_zero_amp(machine):
    """Zero/unset readout amplitude -> the absolute power is UNDEFINED (ValueError),
    and snapshot() degrades that qubit's readout_power_dbm to None."""
    backend = QMBackend(machine)
    view = backend.device.component("q4")
    q = machine.qubits["q4"]
    amp0 = q.resonator.operations["readout"].amplitude
    try:
        q.resonator.operations["readout"].amplitude = 0.0
        with pytest.raises(ValueError, match="absolute power undefined"):
            _ = view.readout_power_dbm
        assert backend.device.snapshot()["q4"]["readout_power_dbm"] is None
    finally:
        q.resonator.operations["readout"].amplitude = amp0


def test_drive_power_dbm_roundtrip(machine):
    """v0.11 drive twin: same bidirectional grid solve as readout, on the xy
    channel + the saturation op; drive_amp is the coupled residual."""
    backend = QMBackend(machine)
    view = backend.device.component("q4")
    q = machine.qubits["q4"]
    if "saturation" not in q.xy.operations:
        pytest.skip("loaded quam_state has no saturation op on q4")
    fs0 = q.xy.opx_output.full_scale_power_dbm
    amp0 = q.xy.operations["saturation"].amplitude
    try:
        view.drive_power_dbm = -21.0
        assert view.drive_power_dbm == pytest.approx(-21.0, abs=1e-6)
        assert q.xy.opx_output.full_scale_power_dbm == -11  # grid floor at weak drive
        assert view.drive_amp == pytest.approx(10 ** ((-21.0 + 11) / 20.0))

        view.drive_power_dbm = -2.0
        assert view.drive_power_dbm == pytest.approx(-2.0, abs=1e-6)
        assert q.xy.opx_output.full_scale_power_dbm == 7  # back UP: bidirectional
        assert 0.354 < view.drive_amp <= 0.5
    finally:
        q.xy.opx_output.full_scale_power_dbm = fs0
        q.xy.operations["saturation"].amplitude = amp0


def test_drive_power_dbm_undefined_on_zero_amp(machine):
    backend = QMBackend(machine)
    view = backend.device.component("q4")
    q = machine.qubits["q4"]
    if "saturation" not in q.xy.operations:
        pytest.skip("loaded quam_state has no saturation op on q4")
    amp0 = q.xy.operations["saturation"].amplitude
    try:
        q.xy.operations["saturation"].amplitude = 0.0
        with pytest.raises(ValueError, match="absolute power undefined"):
            _ = view.drive_power_dbm
        assert backend.device.snapshot()["q4"]["drive_power_dbm"] is None
    finally:
        q.xy.operations["saturation"].amplitude = amp0


def test_power_context_matches_the_view(machine):
    backend = QMBackend(machine)
    ctx = backend.power_context(["q4", "nonexistent"])
    q = machine.qubits["q4"]
    assert ctx["q4"]["full_scale_power_dbm"] == q.resonator.opx_output.full_scale_power_dbm
    assert ctx["q4"]["readout_amplitude"] == pytest.approx(
        float(q.resonator.operations["readout"].amplitude)
    )
    assert ctx["q4"]["readout_power_dbm"] == pytest.approx(
        backend.device.component("q4").readout_power_dbm
    )
    # the readout LO the data was taken at — stamped only when the channel has
    # one (MW-FEM upconverter; an LF-FEM resonator carries none)
    expected_lo = getattr(q.resonator, "LO_frequency", None)
    if expected_lo is not None:
        assert ctx["q4"]["readout_lo_freq_hz"] == pytest.approx(float(expected_lo))
    else:
        assert "readout_lo_freq_hz" not in ctx["q4"]
    assert ctx["nonexistent"] == {}  # unknown qubit degrades, never raises


def test_absolute_punchout_probe_matches_direct_build(machine):
    """Chain-stepped contract: QMResonatorSpectroscopyPowerChain.probe() builds
    the plain 1D resonator-spectroscopy program at the current device state — the
    core run() loop solves the chain per point and swaps in the 1D detuning axis."""
    from qm import generate_qua_script

    from customized.probes._lib import select_qubits
    from customized.probes import resonator_spectroscopy as res_spec_probe
    from customized.scqo.experiments.resonator_spectroscopy_power_chain import (
        QMResonatorSpectroscopyPowerChain,
    )

    backend = QMBackend(machine)
    config = machine.generate_config()

    def script(prog):
        return "\n".join(
            ln for ln in generate_qua_script(prog, config).splitlines() if "generated at" not in ln
        )

    qubits_names = ["q4", "q5"]
    qubits = select_qubits(machine, qubits_names, multiplexed=True)

    exp = QMResonatorSpectroscopyPowerChain(
        backend,
        QMResonatorSpectroscopyPowerChain.Parameters(
            targets=qubits_names, max_power_dbm=-15.0, min_power_dbm=-45.0, num_averages=100
        ),
    )
    axes = exp.define_sweep()
    # uniform grid straight from the core
    power_dbm = np.asarray(axes["power_dbm"])
    steps = np.diff(power_dbm)
    assert np.allclose(steps, steps[0])
    # mimic one per-point call (the run loop swaps in the 1D axis)
    exp.sweep_axes = {"detuning_hz": axes["detuning_hz"]}
    prog, _ = exp.probe()

    direct, _ = res_spec_probe.build_program(
        machine, qubits, dfs=axes["detuning_hz"], num_shots=100,
    )
    assert script(prog) == script(direct)


def test_power_amp_probe_builds_with_new_loop_order(machine):
    """The fast absolute punchout (amp -> averages -> freq loop order, middle-axis
    stream averaging) compiles to a QUA program: prefactors 10**((P - max)/20)
    relative to the window top the core run() solved the chain for (top exactly
    1.0, all <= 1 — inside QUA's amplitude_scale range), and
    resonator_relaxation_time_ns reaches the program (the generated script changes
    when it is set)."""
    from qm import generate_qua_script

    from customized.scqo.experiments.resonator_spectroscopy_power_amp import (
        QMResonatorSpectroscopyPowerAmp,
    )

    backend = QMBackend(machine)
    config = machine.generate_config()

    def script(params):
        exp = QMResonatorSpectroscopyPowerAmp(
            backend, QMResonatorSpectroscopyPowerAmp.Parameters(**params)
        )
        exp.sweep_axes = exp.define_sweep()
        # the axis is the absolute window straight from the core
        power_dbm = np.asarray(exp.sweep_axes["power_dbm"])
        assert power_dbm[0] == -50.0 and power_dbm[-1] == -20.0  # the defaults
        prog, axes = exp.probe()
        assert set(axes) == {"qubit", "detuning", "power"}
        return "\n".join(
            ln for ln in generate_qua_script(prog, config).splitlines() if "generated at" not in ln
        )

    base = dict(targets=["q4"], num_power_points=5, num_freq_points=3, num_averages=10)
    default = script(base)
    overridden = script({**base, "resonator_relaxation_time_ns": 25000.0})
    assert default != overridden  # the relaxation override reaches the QUA program
