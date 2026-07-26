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


# --------------------------------------------------------- saturation (spec) drive
def test_saturation_amp_roundtrip():
    q = _qubit()
    q.xy.operations["saturation"] = SimpleNamespace(amplitude=0.25)
    assert quam_fields.get_saturation_amp(q) == pytest.approx(0.25)
    quam_fields.set_saturation_amp(q, 0.125)
    assert q.xy.operations["saturation"].amplitude == pytest.approx(0.125)
    assert isinstance(q.xy.operations["saturation"].amplitude, float)


def test_saturation_amp_missing_operation_raises_keyerror():
    """A qubit without a saturation op surfaces as unknown (KeyError is what the
    scqo backend's _read_or_none catches)."""
    q = _qubit()
    with pytest.raises(KeyError):
        quam_fields.get_saturation_amp(q)


# ------------------------------------------------------- readout duration / window
class _ReadoutPulse:
    """QUAM ReadoutPulse stand-in with REAL reference semantics: attribute reads
    resolve the default-weights reference against the CURRENT length (exactly
    what quam does); the raw slot keeps the stored form for assertions."""

    def __init__(self, length=2000, weights=None, angle=0.35):
        self.length = length
        self.integration_weights_angle = angle
        self._raw_weights = weights if weights is not None else (
            quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF)

    @property
    def integration_weights(self):
        if self._raw_weights == quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF:
            return [(1, self.length)]
        return self._raw_weights

    @integration_weights.setter
    def integration_weights(self, value):
        self._raw_weights = value


def _readout_qubit(length=2000, weights=None, angle=0.35):
    q = _qubit()
    q.resonator.operations = {"readout": _ReadoutPulse(length, weights, angle)}
    return q


def test_readout_duration_roundtrip():
    q = _readout_qubit(length=2000)
    assert quam_fields.get_readout_duration(q) == pytest.approx(2.0e-6)
    quam_fields.set_readout_duration(q, 4.0e-6)
    assert q.resonator.operations["readout"].length == 4000


def test_duration_grow_preserves_window_numerically():
    """Growing the pulse must NOT grow the window (Qblox parity: independent
    knobs) — the old full-pulse window gets zero-padded into the new length."""
    q = _readout_qubit(length=2000)  # default weights: window == 2000
    quam_fields.set_readout_duration(q, 3.0e-6)
    pulse = q.resonator.operations["readout"]
    assert pulse.length == 3000
    assert pulse._raw_weights == [(1.0, 2000), (0.0, 1000)]
    assert quam_fields.get_readout_integration(q) == pytest.approx(2.0e-6)


def test_duration_shrink_clamps_window_to_default_ref():
    q = _readout_qubit(length=2000)  # window == 2000
    quam_fields.set_readout_duration(q, 1.0e-6)
    pulse = q.resonator.operations["readout"]
    assert pulse.length == 1000
    # window clamped to the full (new) pulse -> normalized back to the reference
    assert pulse._raw_weights == quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF
    assert quam_fields.get_readout_integration(q) == pytest.approx(1.0e-6)


def test_duration_shrink_partial_keeps_shorter_window():
    q = _readout_qubit(length=2000, weights=[(1.0, 800), (0.0, 1200)])
    quam_fields.set_readout_duration(q, 1.0e-6)  # window 800 still fits
    assert q.resonator.operations["readout"]._raw_weights == [(1.0, 800), (0.0, 200)]
    quam_fields.set_readout_duration(q, 4.0e-7)  # 400 ns < window -> clamp
    assert (q.resonator.operations["readout"]._raw_weights
            == quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF)
    assert quam_fields.get_readout_integration(q) == pytest.approx(4.0e-7)


def test_set_window_zero_pads_and_preserves_angle():
    q = _readout_qubit(length=2000, angle=6.13)
    quam_fields.set_readout_integration(q, 1.0e-6)
    pulse = q.resonator.operations["readout"]
    assert pulse._raw_weights == [(1.0, 1000), (0.0, 1000)]
    assert pulse.integration_weights_angle == pytest.approx(6.13)  # untouched
    assert quam_fields.get_readout_integration(q) == pytest.approx(1.0e-6)


def test_set_window_equal_to_pulse_restores_reference():
    q = _readout_qubit(length=2000, weights=[(1.0, 1000), (0.0, 1000)])
    quam_fields.set_readout_integration(q, 2.0e-6)
    assert (q.resonator.operations["readout"]._raw_weights
            == quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF)


def test_set_window_beyond_pulse_refused():
    q = _readout_qubit(length=2000)
    with pytest.raises(ValueError, match="exceeds the readout pulse"):
        quam_fields.set_readout_integration(q, 3.0e-6)
    # nothing was written
    assert (q.resonator.operations["readout"]._raw_weights
            == quam_fields.DEFAULT_INTEGRATION_WEIGHTS_REF)


def test_off_grid_durations_refused():
    q = _readout_qubit(length=2000)
    for bad in (1.002e-6, 2.0001e-6, -2.0e-6, 0.0):  # 1002 ns off the 4 ns grid, etc.
        with pytest.raises(ValueError, match="multiple of 4 ns"):
            quam_fields.set_readout_duration(q, bad)
        with pytest.raises(ValueError, match="multiple of 4 ns"):
            quam_fields.set_readout_integration(q, bad)
    assert q.resonator.operations["readout"].length == 2000  # untouched


def test_window_getter_reads_float_sample_weights():
    """Per-sample float weights (1 ns each): the window is the nonzero count."""
    q = _readout_qubit(length=2000, weights=[1.0] * 500 + [0.0] * 1500)
    assert quam_fields.get_readout_integration(q) == pytest.approx(5.0e-7)


def test_qm_channel_views_use_the_shared_mapping():
    """The scqo CHANNEL views and quam_fields produce identical QUAM writes (the
    dedup). Since the greenfield split there is one view per channel KIND over
    the SAME QUAM qubit — the drive knobs on q.xy, the readout knobs on
    q.resonator, the standing bias on q.z — so each is constructed with its own
    entity name and subtree, exactly as component() does."""
    from customized.scqo.backend import (
        QMDriveChannel, QMFluxChannel, QMReadoutChannel,
    )

    q = _qubit(f_01=5.0e9, xy_rf=5.1e9)
    q.name = "q0"
    q.z = SimpleNamespace(flux_point="joint", joint_offset=0.0)

    drive = QMDriveChannel("q0_xy", q)
    drive.drive_freq_hz = 5.002e9
    assert q.f_01 == pytest.approx(5.002e9)
    assert q.xy.RF_frequency == pytest.approx(5.102e9)

    drive.pi_amp = 0.3
    assert q.xy.operations["x180"].amplitude == pytest.approx(0.3)

    readout = QMReadoutChannel("q0_ro", q)
    readout.readout_freq_hz = 6.4e9
    assert q.resonator.RF_frequency == pytest.approx(6.4e9)
    assert q.resonator.f_01 == pytest.approx(6.4e9)

    q.resonator.operations = {"readout": _ReadoutPulse(length=2000, angle=6.13)}
    readout.readout_duration_s = 4.0e-6
    assert q.resonator.operations["readout"].length == 4000
    readout.readout_integration_s = 2.0e-6
    assert q.resonator.operations["readout"]._raw_weights == [(1.0, 2000), (0.0, 2000)]
    assert readout.readout_integration_s == pytest.approx(2.0e-6)

    # the flux view's single knob lands on the offset z.flux_point SELECTS
    flux = QMFluxChannel("q0_z", q)
    flux.idle_flux = -0.031
    assert q.z.joint_offset == pytest.approx(-0.031)
    assert flux.idle_flux == pytest.approx(-0.031)


def test_qm_flux_view_serves_a_coupler_without_a_qubit():
    """The SECOND vendor shape behind one neutral knob: a coupler's flux channel
    has no QUAM qubit at all — the view is built on the TunableCoupler directly
    and idle_flux follows its own flux-point vocabulary (off -> decouple_offset)."""
    from customized.scqo.backend import QMFluxChannel

    coupler = SimpleNamespace(id="coupler_q1_q2", flux_point="off",
                              decouple_offset=0.0, interaction_offset=0.2)
    view = QMFluxChannel("q1_q2_c_z", None, coupler)
    assert view.qubit is None and view.vendor is coupler

    view.idle_flux = 0.07
    assert coupler.decouple_offset == pytest.approx(0.07)
    assert coupler.interaction_offset == pytest.approx(0.2)  # the OFF point only
    coupler.flux_point = "on"
    assert view.idle_flux == pytest.approx(0.2)  # the point selects the offset


def test_drag_beta_writes_dragcosine_and_skips_alias():
    """set_drag_beta writes the x180_DragCosine storage node (QUAM stores DRAG as
    alpha) and leaves string-reference aliases untouched; get reads it back."""
    class _Op:
        def __init__(self, alpha=0.0, amplitude=0.1):
            self.alpha = alpha
            self.amplitude = amplitude

    q = SimpleNamespace(xy=SimpleNamespace(operations={
        "x180_DragCosine": _Op(), "x90_DragCosine": _Op(),
        "x180": "#./x180_DragCosine",  # a string-reference alias
    }))
    quam_fields.set_drag_beta(q, -0.75)
    assert q.xy.operations["x180_DragCosine"].alpha == pytest.approx(-0.75)
    assert q.xy.operations["x90_DragCosine"].alpha == pytest.approx(-0.75)  # lock_x90 default True
    assert q.xy.operations["x180"] == "#./x180_DragCosine"  # alias untouched
    assert quam_fields.get_drag_beta(q) == pytest.approx(-0.75)


# ----------------------------------------------------------------- depletion wait
def _resonator(depletion_time=16):
    return SimpleNamespace(resonator=SimpleNamespace(depletion_time=depletion_time))


def test_readout_depletion_roundtrips_on_the_4ns_grid():
    """Seconds <-> ns, rounded (not refused) onto the QUA wait grid: this is a
    policy wait resonator_spectroscopy writes as depletion_factor / (2 pi x
    kappa_tot_hz), which is never on the grid by luck -- the same rule
    set_thermalization_time already settled. Stored as int: QUAM types the field
    that way and does depletion_time // 4."""
    q = _resonator()
    quam_fields.set_readout_depletion(q, 795.77e-9)  # 5 / (2 pi x 1 MHz)

    assert q.resonator.depletion_time == 792  # 795.77 -> 792, a multiple of 4
    assert isinstance(q.resonator.depletion_time, int)
    assert quam_fields.get_readout_depletion(q) == pytest.approx(792e-9)


def test_zero_depletion_is_legal_but_negative_is_not():
    """0 is a real calibrated answer ("this resonator needs no settle") and must
    survive, unlike a reset wait where 0 is nonsense. Only negative is refused."""
    q = _resonator()
    quam_fields.set_readout_depletion(q, 0.0)
    assert q.resonator.depletion_time == 0

    with pytest.raises(ValueError, match="negative"):
        quam_fields.set_readout_depletion(q, -1e-9)


def test_depletion_needs_no_custom_transmon_class():
    """Unlike thermalization_time_s, which REQUIRES a Thermalizing*Transmon
    because QUAM derives its wait as factor x T1 with nowhere to store an
    absolute one. depletion_time is a plain settable field on every stock
    ReadoutResonator, so this knob needs no per-device migration."""
    q = _resonator(depletion_time=16)  # QUAM's own default, ungoverned until now
    assert quam_fields.get_readout_depletion(q) == pytest.approx(16e-9)
