"""Tests for the scqo QM backend (customized.scqo).

Three tiers:

* ``_to_canonical`` and catalog registration are pure (no instrument, no QUAM).
* The greenfield ENTITY surface (component resolution, the per-kind channel
  views, the composite pair knobs, snapshot/power_context) runs against the stub
  QUAM tree from ``conftest.py`` — always, on every machine.
* Probe equivalence and the absolute-power chain solve load the LIVE
  ``quam_state/`` and skip when it does not match the root class currently
  toggled in ``quam_config/my_quam.py``.
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


# ------------------------------------------------ entity surface (stub QUAM tree)

def test_component_resolves_channel_entities_per_kind(backend, stub_machine):
    """One view class per CHANNEL KIND over the SAME QUAM qubit: the three names
    a qubit's channels carry land on q.xy / q.resonator / q.z, and each view's
    ``.name`` is the ENTITY name while the vendor object is the subtree."""
    q1 = stub_machine.qubits["q1"]

    xy = backend.device.component("q1_xy")
    ro = backend.device.component("q1_ro")
    z = backend.device.component("q1_z")

    assert (xy.kind, ro.kind, z.kind) == ("drive", "readout", "flux")
    assert (xy.name, ro.name, z.name) == ("q1_xy", "q1_ro", "q1_z")
    assert xy.vendor is q1.xy and ro.vendor is q1.resonator and z.vendor is q1.z
    assert xy.qubit is q1 and ro.qubit is q1 and z.qubit is q1


def test_component_refuses_everything_that_carries_no_knobs(backend):
    """The contract scqo degrades gracefully against: a KeyError, naming what to
    address instead, for an unknown name, a MODE, a LINE, and a resonator mode
    (knobs live on channels since the greenfield split)."""
    with pytest.raises(KeyError, match="not in this device's roster"):
        backend.device.component("nope")
    with pytest.raises(KeyError, match="q1_ro"):
        backend.device.component("q1")       # a mode: address its channels
    with pytest.raises(KeyError, match="q1_z"):
        backend.device.component("q1")
    with pytest.raises(KeyError):
        backend.device.component("fl")       # a line
    with pytest.raises(KeyError):
        backend.device.component("q1_res")   # the minted resonator mode


def test_component_names_the_missing_subtree_on_a_fixed_frequency_qubit(backend,
                                                                        roster):
    """q3 is a fixed ``transmon``: the roster declares no flux rider for it, so
    no q3_z exists at all — and if one were declared the vendor hop would fail
    naming the absent subtree rather than returning a half-wired view."""
    assert ("q3", "flux") not in roster.defaults
    assert backend.device.component("q3_ro").kind == "readout"


def test_flux_channel_serves_both_vendor_shapes(backend, stub_machine):
    """``idle_flux`` over a qubit's FluxLine AND over the pair's TunableCoupler —
    the coupler's STANDING bias is an ordinary knob on the COUPLER MODE's own
    flux channel (the pair-level coupler_decouple_v field is gone)."""
    q1_z = backend.device.component("q1_z")
    q1_z.idle_flux = -0.042
    assert stub_machine.qubits["q1"].z.joint_offset == pytest.approx(-0.042)

    coupler_z = backend.device.component("q1_q2_c_z")
    assert coupler_z.qubit is None                      # not a QUAM qubit at all
    assert coupler_z.vendor is stub_machine.qubit_pairs["coupler_q1_q2"].coupler
    coupler_z.idle_flux = 0.031                         # flux_point 'off'
    assert coupler_z.vendor.decouple_offset == pytest.approx(0.031)


def test_channel_views_round_trip_the_neutral_knobs(backend, stub_machine):
    """Neutral get/set maps onto QUAM through customized.quam_fields; a
    drive_freq_hz write shifts both f_01 and xy.RF_frequency."""
    q2 = stub_machine.qubits["q2"]
    xy = backend.device.component("q2_xy")
    ro = backend.device.component("q2_ro")

    rf0 = float(q2.xy.RF_frequency)
    xy.drive_freq_hz = 5.102e9
    assert float(q2.f_01) == pytest.approx(5.102e9)
    assert float(q2.xy.RF_frequency) == pytest.approx(rf0 + 2e6)

    xy.pi_amp = 0.123
    assert xy.pi_amp == pytest.approx(0.123)
    xy.pi_duration_s = 4.0e-8
    assert q2.xy.operations["x180"].length == 40
    with pytest.raises(ValueError, match="multiple of 4 ns"):
        xy.pi_duration_s = 4.2e-8  # the QM pulse grid REFUSES, never rounds

    ro.readout_freq_hz = 6.25e9
    assert float(q2.resonator.RF_frequency) == pytest.approx(6.25e9)
    assert float(q2.resonator.f_01) == pytest.approx(6.25e9)
    ro.readout_amp = 0.111
    assert float(q2.resonator.operations["readout"].amplitude) == pytest.approx(0.111)
    ro.readout_threshold = -1.5e-4
    assert q2.resonator.operations["readout"].threshold == pytest.approx(-1.5e-4)


def test_thermalization_time_round_trips_on_the_qubit(backend, stub_machine):
    """The reset wait is a DRIVE-channel knob neutrally, but it lives on the
    QUAM qubit (not q.xy) — and it is rounded to the 4 ns QUA wait grid rather
    than refused like pi_duration_s, because it is a policy wait, not a
    calibrated pulse."""
    q2 = stub_machine.qubits["q2"]
    xy = backend.device.component("q2_xy")

    assert xy.thermalization_time_s is None  # never calibrated == unset
    xy.thermalization_time_s = 3.715492e-4
    assert q2.thermalization_time_ns == 371548  # floor to the 4 ns grid
    assert xy.thermalization_time_s == pytest.approx(3.71548e-4)

    with pytest.raises(ValueError, match="must be positive"):
        xy.thermalization_time_s = 0.0


def test_thermalization_time_refuses_a_stock_quam_class(backend, stub_machine):
    """Stock QUAM derives the wait as factor x T1 through a READ-ONLY property,
    so there is nowhere to store an absolute one. The refusal must name the fix
    (the qubit's state.json __class__) instead of silently doing nothing."""
    del stub_machine.qubits["q2"].thermalization_time_ns  # a stock transmon
    xy = backend.device.component("q2_xy")

    assert xy.thermalization_time_s is None
    with pytest.raises(NotImplementedError, match="Thermalizing"):
        xy.thermalization_time_s = 2e-4


def test_per_run_override_sets_and_reverts_exactly(backend, stub_machine, roster):
    """The per-run override is baked into the compiled program, so bracketing
    the BUILD is enough — and the revert must be exact, including restoring
    "never calibrated" rather than fabricating a value."""
    from scqo.experiments import get

    from conftest import make_experiment

    cls = get("qubit_relaxation")
    q1, q2 = stub_machine.qubits["q1"], stub_machine.qubits["q2"]
    q1.thermalization_time_ns = 100_000  # q1 calibrated, q2 never touched

    seen = {}
    exp = make_experiment(cls, backend, roster,
                          cls.Parameters(targets=["q1", "q2"],
                                         thermalization_time_ns=8_000.0))
    with backend._thermalization_override(exp):
        seen = {"q1": q1.thermalization_time_ns, "q2": q2.thermalization_time_ns}
    assert seen == {"q1": 8_000, "q2": 8_000}
    assert q1.thermalization_time_ns == 100_000  # exact revert
    assert q2.thermalization_time_ns is None     # restored to unset, not 0

    # no override -> the standing QUAM values are left completely alone
    plain = make_experiment(cls, backend, roster, cls.Parameters(targets=["q1"]))
    with backend._thermalization_override(plain):
        assert q1.thermalization_time_ns == 100_000


def test_per_run_override_expands_a_pair_to_its_member_qubits(backend, stub_machine,
                                                              roster):
    """A composite target carries no drive channel of its own; the reset happens
    on its MEMBER modes, resolved through the roster (the QUAM pair is named
    after its coupler, so a name-based shortcut would miss)."""
    from scqo.experiments import get

    from conftest import make_experiment

    cls = get("pair_zz_coupler")
    exp = make_experiment(cls, backend, roster,
                          cls.Parameters(targets=["q1_q2"],
                                         thermalization_time_ns=12_000.0))
    with backend._thermalization_override(exp):
        assert stub_machine.qubits["q1"].thermalization_time_ns == 12_000
        assert stub_machine.qubits["q2"].thermalization_time_ns == 12_000


def test_snapshot_reports_the_bound_knobs_per_entity(backend):
    """The pull-mode seed source: every realized channel reports exactly the
    knobs the fieldmap BINDS for its kind, and the composite reports the
    per-operation knobs the ROSTER compiled for it."""
    from customized.scqo.fieldmap import FIELD_BINDINGS

    snap = backend.device.snapshot()
    assert set(snap["q1_xy"]) == set(FIELD_BINDINGS["drive"])
    assert set(snap["q1_ro"]) == set(FIELD_BINDINGS["readout"])
    assert set(snap["q1_z"]) == {"idle_flux"}
    # the composite's names are per-OPERATION, instantiated from the roster
    assert "cz_coupler_flux" in snap["q1_q2"]
    assert snap["q1_q2"]["cz_coupler_flux"] == pytest.approx(-0.125)
    # an Unrealized composite knob degrades to None instead of crashing the seed
    assert snap["q1_q2"]["cz_duration_s"] is None


def test_composite_view_reads_and_writes_the_gate_knobs(backend, stub_machine):
    """The QM pair surface Qblox has no counterpart for: per-operation knobs by
    full field name, resolved against the roster's DECLARED operations and the
    QUAM gate macro (matched case-insensitively — QUAM spells it "CZ")."""
    macro = stub_machine.qubit_pairs["coupler_q1_q2"].macros["CZ"]
    pair = backend.device.component("q1_q2")

    assert pair.read_knob("cz_coupler_flux") == pytest.approx(-0.125)
    pair.write_knob("cz_coupler_flux", -0.2)
    assert macro.coupler_flux_pulse.amplitude == pytest.approx(-0.2)

    # virtual Z: rad <-> turns, and the roster's high role (q2) is the QUAM
    # pair's TARGET here — resolved by name, never guessed
    pair.write_knob("cz_vz_high_rad", np.pi)
    assert macro.phase_shift_target == pytest.approx(0.5)
    assert macro.phase_shift_control == pytest.approx(0.0)
    pair.write_knob("cz_vz_low_rad", -np.pi / 2)
    assert macro.phase_shift_control == pytest.approx(-0.25)
    assert pair.read_knob("cz_vz_low_rad") == pytest.approx(-np.pi / 2)


def test_composite_view_refuses_undeclared_and_unrealized_knobs(backend):
    """Exact-cause errors: an undeclared operation names the declared set, a
    non-knob name names the legal suffixes, and a suffix QM cannot realize
    raises NotImplementedError with its reason (never a silent no-op)."""
    pair = backend.device.component("q1_q2")

    with pytest.raises(KeyError, match="not declared on this composite"):
        pair.read_knob("iswap_coupler_flux")
    with pytest.raises(KeyError, match="not a per-operation knob"):
        pair.read_knob("coupler_flux")
    with pytest.raises(NotImplementedError, match="FLUX-activated"):
        pair.read_knob("cz_drive_freq_hz")
    with pytest.raises(NotImplementedError):
        pair.write_knob("cz_duration_s", 40e-9)


def test_power_context_matches_the_views(backend, stub_machine):
    """Run-record provenance, addressed by MODE name: each target's readout and
    drive chains resolved through the roster's DEFAULT channels, never failing."""
    ctx = backend.power_context(["q1", "nonexistent"])
    q1 = stub_machine.qubits["q1"]

    assert ctx["q1"]["full_scale_power_dbm"] == q1.resonator.opx_output.full_scale_power_dbm
    assert ctx["q1"]["readout_amplitude"] == pytest.approx(
        float(q1.resonator.operations["readout"].amplitude))
    assert ctx["q1"]["readout_power_dbm"] == pytest.approx(
        backend.device.component("q1_ro").readout_power_dbm)
    assert ctx["q1"]["drive_power_dbm"] == pytest.approx(
        backend.device.component("q1_xy").drive_power_dbm)
    assert ctx["q1"]["readout_lo_freq_hz"] == pytest.approx(
        float(q1.resonator.LO_frequency))
    assert ctx["nonexistent"] == {}  # unknown target degrades, never raises


def test_readout_power_dbm_solves_the_chain_bidirectionally(backend, stub_machine):
    """Absolute power: the setter re-solves (full_scale_power_dbm, amplitude) with
    the SMALLEST grid full-scale keeping amp <= 0.5 — bidirectional (a lower target
    lowers full scale again, unlike the bare power_tools helper)."""
    view = backend.device.component("q1_ro")
    res = stub_machine.qubits["q1"].resonator

    view.readout_power_dbm = -2.0
    assert view.readout_power_dbm == pytest.approx(-2.0, abs=1e-6)
    assert res.opx_output.full_scale_power_dbm == 7  # smallest grid value >= -2+6.02
    assert 0.354 < float(res.operations["readout"].amplitude) <= 0.5

    view.readout_power_dbm = -24.3
    assert res.opx_output.full_scale_power_dbm == -11  # back DOWN to the grid floor
    assert float(res.operations["readout"].amplitude) == pytest.approx(
        10 ** ((-24.3 + 11) / 20.0))

    with pytest.warns(UserWarning, match="canonical operating point"):
        view.readout_power_dbm = 10.0
    assert res.opx_output.full_scale_power_dbm == 16

    # zero amplitude -> the absolute power is UNDEFINED, and snapshot degrades it
    res.operations["readout"].amplitude = 0.0
    with pytest.raises(ValueError, match="absolute power undefined"):
        _ = view.readout_power_dbm
    assert backend.device.snapshot()["q1_ro"]["readout_power_dbm"] is None


def test_drive_power_dbm_solves_the_same_chain_on_xy(backend, stub_machine):
    """The drive twin: same grid solve on the xy channel + the saturation op;
    drive_amp is the coupled residual."""
    view = backend.device.component("q1_xy")
    xy = stub_machine.qubits["q1"].xy

    view.drive_power_dbm = -21.0
    assert xy.opx_output.full_scale_power_dbm == -11  # grid floor at weak drive
    assert view.drive_amp == pytest.approx(10 ** ((-21.0 + 11) / 20.0))

    view.drive_power_dbm = -2.0
    assert xy.opx_output.full_scale_power_dbm == 7  # back UP: bidirectional
    assert 0.354 < view.drive_amp <= 0.5

    xy.operations["saturation"].amplitude = 0.0
    with pytest.raises(ValueError, match="absolute power undefined"):
        _ = view.drive_power_dbm
    assert backend.device.snapshot()["q1_xy"]["drive_power_dbm"] is None


def test_recording_device_seeds_and_pushes_through_the_channel_entities(backend,
                                                                        roster):
    """End to end the way a Session drives it: RecordingDevice seeds its runtime
    config from the vendor (pull) and a neutral write lands on QUAM."""
    from conftest import recording_device

    device = recording_device(backend, roster)
    assert device.channel("q1", "readout").readout_freq_hz == pytest.approx(6.10e9)
    assert device.channel("q1_q2_c", "flux").idle_flux == pytest.approx(0.0)

    device.channel("q1", "drive").pi_amp = 0.31
    assert backend.device.component("q1_xy").pi_amp == pytest.approx(0.31)


def roster_toml_for(machine) -> str:
    """A schema-3 roster describing whatever QUAM tree is passed in.

    The roster describes the SAMPLE, so a fixture for a LIVE vendor state has to
    be generated from it: one mode per QUAM qubit (``flux_transmon`` when it
    carries a z subtree, else a fixed ``transmon`` — a flux rider on a fixed
    transmon is a load error, which is exactly the capability-by-construction
    rule), one multiplexed readout feedline, a drive wire each, a flux wire for
    every z-capable mode INCLUDING the couplers, and one composite per QUAM
    qubit_pair named ``<low>_<high>`` — so the backend has to make the
    membership join that QM's coupler-named pairs require.
    """
    modes, composites, lines, flux_riders = [], [], [], []
    lines.append("[lines.fl]\nreadout = ["
                 + ", ".join(f'"{n}"' for n in machine.qubits) + "]")
    for name, q in machine.qubits.items():
        has_z = getattr(q, "z", None) is not None
        kind = "flux_transmon" if has_z else "transmon"
        modes.append(f'[modes.{name}]\nkind = "{kind}"')
        lines.append(f'[lines.xy_{name}]\ndrive = ["{name}"]')
        if has_z:
            flux_riders.append(name)
    for key, qp in (getattr(machine, "qubit_pairs", {}) or {}).items():
        low, high = qp.qubit_control.name, qp.qubit_target.name
        block = [f"[composites.{low}_{high}]", 'kind = "qubit_pair"',
                 f'high = "{high}"', f'low = "{low}"']
        if getattr(qp, "coupler", None) is not None:
            modes.append(f'[modes.{key}]\nkind = "flux_transmon"')  # QM names
            flux_riders.append(key)                                 # it after
            block.append(f'coupler = "{key}"')                      # the pair
        composites.append("\n".join(block))
    lines += [f'[lines.z_{t}]\nflux = ["{t}"]' for t in flux_riders]
    return "\n\n".join(["schema = 3", *modes, *composites, *lines]) + "\n"


def test_roster_toml_for_a_quam_tree_parses(stub_machine):
    """The live-state roster generator above is only exercised when the toggle
    matches, so pin it here against the stub tree: fixed-frequency qubits get no
    flux rider, the coupler becomes an ordinary mode with its own flux wire, and
    the pair composite carries the coupler role."""
    from scqo.roster import parse_components

    generated = parse_components(roster_toml_for(stub_machine))
    assert generated.entities["q3"].kind == "transmon"
    assert ("q3", "flux") not in generated.defaults      # no flux on a fixed one
    assert ("coupler_q1_q2", "flux") in generated.defaults
    pair = generated.entities["q1_q2"]
    assert pair.roles["high"] == ("q2",) and pair.roles["low"] == ("q1",)
    assert pair.roles["coupler"] == ("coupler_q1_q2",)

    # ...and every name it declares resolves through the backend against the
    # same tree — which is what the skipped live-machine tests below rely on
    generated_backend = QMBackend(stub_machine, roster=generated)
    assert set(generated_backend.device.components()) == (
        set(generated.channels()) | set(generated.composites()))
    assert generated_backend.device.component(
        generated.default_channel("q1", "readout")).kind == "readout"


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


@pytest.fixture(scope="module")
def live_roster(machine):
    """A schema-3 roster mirroring whatever the loaded quam_state holds."""
    from scqo.roster import parse_components

    return parse_components(roster_toml_for(machine))


def test_probe_matches_direct_build(machine, live_roster):
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

    backend = QMBackend(machine, roster=live_roster)
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


def test_live_readout_window_round_trip(machine, live_roster):
    """The window accessors against a REAL QUAM ReadoutPulse (its default-weights
    reference semantics are what the stub only mimics) — restored afterwards."""
    backend = QMBackend(machine, roster=live_roster)
    view = backend.device.component(live_roster.default_channel("q4", "readout"))
    pulse = machine.qubits["q4"].resonator.operations["readout"]
    length_ns = int(pulse.length)
    if pulse.integration_weights != [(1, length_ns)]:
        pytest.skip("q4's readout weights are not in the default-reference form")
    half = (length_ns // 2 // 4 * 4) * 1e-9
    try:
        view.readout_integration_s = half
        assert pulse.integration_weights[0][0] == 1.0
        assert view.readout_integration_s == pytest.approx(half)
    finally:
        view.readout_integration_s = length_ns * 1e-9  # restore the reference form


def test_absolute_punchout_probe_matches_direct_build(machine, live_roster):
    """Chain-stepped contract: QMResonatorSpectroscopyPowerChain.probe() builds
    the plain 1D resonator-spectroscopy program at the current device state — the
    core run() loop solves the chain per point and swaps in the 1D detuning axis."""
    from qm import generate_qua_script

    from customized.probes._lib import select_qubits
    from customized.probes import resonator_spectroscopy as res_spec_probe
    from customized.scqo.experiments.resonator_spectroscopy_power_chain import (
        QMResonatorSpectroscopyPowerChain,
    )

    backend = QMBackend(machine, roster=live_roster)
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


def test_power_amp_probe_builds_with_new_loop_order(machine, live_roster):
    """The fast absolute punchout (amp -> averages -> freq loop order, middle-axis
    stream averaging) compiles to a QUA program: prefactors 10**((P - max)/20)
    relative to the window top the core run() solved the chain for (top exactly
    1.0, all <= 1 — inside QUA's amplitude_scale range), and
    readout_depletion_ns reaches the program (the generated script changes
    when it is set)."""
    from conftest import make_experiment
    from qm import generate_qua_script

    from customized.scqo.experiments.resonator_spectroscopy_power_amp import (
        QMResonatorSpectroscopyPowerAmp,
    )

    backend = QMBackend(machine, roster=live_roster)
    config = machine.generate_config()

    def script(params):
        # make_experiment, not a bare constructor: the ring-down wait is resolved
        # through the neutral device surface now (per-run override -> the
        # readout_depletion_s knob), so the probe needs the channel views a
        # Session would have attached.
        exp = make_experiment(
            QMResonatorSpectroscopyPowerAmp, backend, live_roster,
            QMResonatorSpectroscopyPowerAmp.Parameters(**params))
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
    overridden = script({**base, "readout_depletion_ns": 25000.0})
    assert default != overridden  # the relaxation override reaches the QUA program
