"""Flux-PULSE amplitude validation: the volts -> amplitude_scale conversion.

A flux pulse probe emits ``play("const" * amp(v / reference))``, so the stored
``const`` amplitude is the divisor and QUA bounds the result to (-2, 2). Three
ways that goes wrong, each SILENT on hardware:

1. the ``const`` amplitude breaks the ``rail/2`` convention — too small caps the
   reachable window with no error, too large clips inside the DAC;
2. the requested excursion needs ``|amplitude_scale| >= 2``;
3. ``idle + excursion`` exceeds the rail — the DAC emits the SUM, and this is
   the one nothing in this repo checked before.

The QM simulator does not show clipping, so every one of these has to be a
build-time refusal.
"""

import pytest

from customized.probes._lib import (
    check_flux_pulse_window,
    const_amp_reference,
    dac_rail_v,
    idle_offset_v,
)

from conftest import _flux_line


def _z(amplitude, *, mode="direct", **offsets):
    """A flux line carrying a `const` op on a port of the given output mode."""
    z = _flux_line(**offsets)
    z.opx_output = type("Port", (), {"output_mode": mode})()
    z.operations = {"const": type("Pulse", (), {"amplitude": amplitude})()}
    return z


# ------------------------------------------------------------ the convention

def test_the_convention_holds_on_both_live_chips():
    """5Q4C runs its flux ports direct (rail 0.5) at const 0.25; chipA runs them
    amplified (rail 2.5) at 1.25. The rule is rail/2 on BOTH — it is a real
    convention read off the live states, not an aspiration."""
    assert const_amp_reference(_z(0.25), name="q2") == 0.25
    assert const_amp_reference(_z(1.25, mode="amplified"), name="q1") == 1.25


def test_a_too_small_const_is_refused_with_the_value_to_set():
    """The 5Q4C couplers' 0.15 on a direct port. Silent otherwise: it just caps
    the reachable window at 0.3 V instead of the rail's 0.5 V."""
    with pytest.raises(ValueError, match="half the port's full scale"):
        const_amp_reference(_z(0.15), name="c12")
    with pytest.raises(ValueError, match="0.25"):  # names the fix
        const_amp_reference(_z(0.15), name="c12")


def test_a_too_large_const_is_refused_too():
    """Above rail/2 the stored waveform itself clips at full scale."""
    with pytest.raises(ValueError, match="half the port's full scale"):
        const_amp_reference(_z(0.4), name="q2")


def test_the_convention_is_read_from_the_PORT_not_a_constant():
    """1.25 V is correct on amplified and wrong on direct — the same number,
    refused or accepted by the port's mode. Hardcoding 0.5 would refuse the
    whole chipA flux config."""
    assert dac_rail_v(_z(1.25, mode="amplified")) == 2.5
    assert const_amp_reference(_z(1.25, mode="amplified"), name="q1") == 1.25
    with pytest.raises(ValueError):
        const_amp_reference(_z(1.25), name="q1")  # direct rail: expects 0.25


def test_a_missing_or_zero_const_is_refused_by_name():
    z = _z(0.25)
    z.operations = {}
    with pytest.raises(ValueError, match="no 'const' operation"):
        const_amp_reference(z, name="q2")
    with pytest.raises(ValueError, match="cannot be zero"):
        const_amp_reference(_z(0.0), name="q2")


# ----------------------------------------------------------------- the window

def test_a_normal_window_passes_and_returns_the_reference():
    """The real 5Q4C q2 case: 0.107 V idle, +/-0.05 V window."""
    z = _z(0.25, joint=0.10695)
    reference = check_flux_pulse_window(
        z, name="q2", idle_v=0.10695, amps_v=[-0.05, 0.0, 0.05])
    assert reference == 0.25


def test_an_inexpressible_excursion_is_refused():
    """|v|/reference >= 2 is outside QUA's fixed-point multiplier. With the
    convention that is exactly 'you asked for more than the rail'."""
    z = _z(0.25)
    with pytest.raises(ValueError, match="amplitude_scale"):
        check_flux_pulse_window(z, name="q2", idle_v=0.0, amps_v=[-0.5, 0.5])


def test_the_combined_rail_is_what_actually_bites():
    """A window that is fine on its own still clips once it rides on a standing
    bias, because the DAC emits the SUM. Nothing checked this before, and the
    simulator shows nothing when it happens.

    q2's real numbers: 0.0938 V idle + a +/-0.45 V window reaches 0.544 V, past
    the 0.5 V direct rail.
    """
    z = _z(0.25, joint=0.0938)
    # the window alone is expressible (0.45/0.25 = 1.8 < 2) ...
    check_flux_pulse_window(z, name="q2", idle_v=0.0, amps_v=[-0.45, 0.45])
    # ... but not once it rides on the idle bias
    with pytest.raises(ValueError, match="full scale") as exc:
        check_flux_pulse_window(z, name="q2", idle_v=0.0938, amps_v=[-0.45, 0.45])
    assert "SIMULATOR" in str(exc.value)  # the reason this must refuse, not warn


def test_the_combined_rail_check_is_asymmetric():
    """A positive idle bias eats headroom on the positive side only, so the
    check must test both ends rather than the window's magnitude."""
    z = _z(0.25, joint=0.3)
    with pytest.raises(ValueError, match="full scale"):
        check_flux_pulse_window(z, name="q2", idle_v=0.3, amps_v=[-0.4, 0.4])
    # the same magnitude one-sided downward stays inside the rail
    check_flux_pulse_window(z, name="q2", idle_v=0.3, amps_v=[-0.4, 0.0])


# ------------------------------------------------------------- the idle anchor

def test_the_idle_offset_follows_the_APPLIED_point_not_the_declared_one():
    """``idle_offset_v`` takes the point as an argument on purpose: a probe must
    validate the bias it is applying. Reading ``z.flux_point`` here would rebuild
    the very gap the factory guard closes — note this line DECLARES 'independent'
    while the probes apply 'joint'."""
    z = _flux_line(joint=0.107, flux_point="independent")
    z.independent_offset = 0.084
    assert idle_offset_v(z, "joint") == 0.107
    assert idle_offset_v(z, "independent") == 0.084
    assert idle_offset_v(z, "zero") == 0.0


def test_an_unknown_flux_point_is_refused_rather_than_defaulted():
    with pytest.raises(ValueError, match="selects no offset"):
        idle_offset_v(_flux_line(), "nonsense")
