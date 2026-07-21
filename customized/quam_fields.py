"""Neutral QUAM field accessors — the single place that knows how SCQO's neutral
calibration fields map onto QUAM attribute paths.

Both call sites write through these primitives, so the
``f_01`` / ``resonator.RF_frequency`` / ``xy.operations['x180'].amplitude`` mapping is
defined exactly once:

* the scqo backend's ``QMQubitView`` (``customized/scqo/backend.py``) — neutral get/set;
* the qualibrate ``apply_update`` writebacks (``customized/node/LCH_*/update.py``).

Pure attribute access on a passed QUAM ``qubit``: no qm/quam import here, so this stays
importable without an instrument (and unit-testable with a stub qubit).

Neutral field -> QUAM path
    readout_freq          <-> q.resonator.RF_frequency  (and q.resonator.f_01 when present)
    drive_freq            <-> q.f_01                     (and q.xy.RF_frequency, kept in step)
    pi_amp                <-> q.xy.operations['x180'].amplitude
    readout_duration_s    <-> q.resonator.operations['readout'].length (s <-> ns)
    readout_integration_s <-> ...operations['readout'].integration_weights
                              (window w -> [(1, w), (0, length - w)]; default ref when w == length)
"""

from __future__ import annotations

from typing import Any

#: The operation whose amplitude is the calibrated pi pulse (the neutral ``pi_amp``).
PI_OPERATION = "x180"


# ----------------------------------------------------------------- readout / resonator
def get_readout_freq(qubit: Any) -> float:
    return float(qubit.resonator.RF_frequency)


def set_readout_freq(qubit: Any, value: float) -> None:
    """Set the resonator frequency to an absolute Hz: ``RF_frequency`` and, when the
    resonator carries it, ``f_01`` (the two are kept equal)."""
    value = float(value)
    qubit.resonator.RF_frequency = value
    if hasattr(qubit.resonator, "f_01"):
        qubit.resonator.f_01 = value


def shift_readout_freq(qubit: Any, delta: float) -> None:
    """Shift only the resonator RF frequency by ``delta`` Hz."""
    qubit.resonator.RF_frequency = float(qubit.resonator.RF_frequency) + float(delta)


# ----------------------------------------------------------------------- drive (f_01)
def get_drive_freq(qubit: Any) -> float:
    return float(qubit.f_01)


def _seed_f01_if_unset(qubit: Any) -> None:
    """An uncalibrated qubit has ``f_01`` unset (None) while its drive RF is always known;
    on resonance the two coincide, so seed ``f_01`` from the drive RF before shifting."""
    if qubit.f_01 is None:
        qubit.f_01 = float(qubit.xy.RF_frequency)


def set_drive_freq(qubit: Any, value: float) -> None:
    """Set ``f_01`` to an absolute Hz and shift the xy drive RF by the same delta, so the
    fixed ``f_01`` <-> RF offset is preserved."""
    _seed_f01_if_unset(qubit)
    delta = float(value) - float(qubit.f_01)
    qubit.f_01 = float(value)
    qubit.xy.RF_frequency = float(qubit.xy.RF_frequency) + delta


def shift_drive_freq(qubit: Any, delta: float) -> None:
    """Shift both ``f_01`` and the xy drive RF by ``delta`` Hz (keeps them in step)."""
    _seed_f01_if_unset(qubit)
    delta = float(delta)
    qubit.f_01 = float(qubit.f_01) + delta
    qubit.xy.RF_frequency = float(qubit.xy.RF_frequency) + delta


# ---------------------------------------------------------------------- readout amplitude
#: The readout operation whose amplitude is the neutral ``readout_amp``.
READOUT_OPERATION = "readout"


def get_readout_amp(qubit: Any, operation: str = READOUT_OPERATION) -> float:
    return float(qubit.resonator.operations[operation].amplitude)


def set_readout_amp(qubit: Any, value: float, *, operation: str = READOUT_OPERATION) -> None:
    """Write the readout pulse amplitude (within the current output-power config;
    large power reconfiguration — FEM gain — stays with the qualibrate power node's
    ``set_output_power`` path)."""
    qubit.resonator.operations[operation].amplitude = float(value)


# ----------------------------------------------------- readout duration / window
#: The QUAM reference restoring ``ReadoutPulse``'s default weights
#: ([(1, length)] — window == pulse, following the length by reference). Written
#: back whenever the window equals the pulse so state.json keeps the follow form.
DEFAULT_INTEGRATION_WEIGHTS_REF = "#./default_integration_weights"


def _grid_ns(value_s: float, what: str) -> int:
    """A seconds duration as integer ns, REFUSED unless a positive multiple of
    4 ns (the QM pulse/weights grid — also the portable neutral contract, so a
    value accepted here is accepted verbatim on the Qblox backend too)."""
    ns = float(value_s) * 1e9
    grid = round(ns)
    if abs(ns - grid) > 1e-3 or grid <= 0 or grid % 4:
        raise ValueError(
            f"{what}={value_s!r} s: must be a positive multiple of 4 ns "
            f"(the QM pulse/integration-weights grid; no silent rounding)")
    return int(grid)


def _window_ns(pulse: Any) -> int:
    """The effective integration window: total ns of NONZERO integration weight.

    Default weights resolve to [(1, length)] -> the full pulse; a zero-padded
    constant list -> its support; per-sample float weights (1 ns each) -> the
    nonzero-sample count. Shaped (optimized) weights report their total nonzero
    duration — the window length is well-defined even when the shape is not ours."""
    weights = pulse.integration_weights  # QUAM resolves the default reference
    if weights and isinstance(weights[0], (tuple, list)):
        return int(sum(l for w, l in weights if w))
    return int(sum(1 for w in weights if w))


def _set_weights(pulse: Any, value: Any) -> None:
    """Write the integration_weights slot. quam REFUSES overwriting a reference
    attribute with a plain value — the slot must be released (set to None)
    first; setting TO a reference string needs no release but survives one."""
    pulse.integration_weights = None
    pulse.integration_weights = value


def get_readout_duration(qubit: Any, operation: str = READOUT_OPERATION) -> float:
    """Readout pulse length in seconds (QUAM stores ns). Divided by the EXACT
    1e9 (never * 1e-9): division rounds correctly, so 2000 ns reads back as the
    same float the literal 2e-6 parses to — no 1-ulp echo records."""
    return float(qubit.resonator.operations[operation].length) / 1e9


def set_readout_duration(qubit: Any, value: float, *,
                         operation: str = READOUT_OPERATION) -> None:
    """Set the readout pulse length (seconds, multiple of 4 ns).

    The integration weights must span exactly the pulse, so they are rebuilt
    around the new length with the current window PRESERVED numerically —
    clamped down only when the pulse shrinks below it (the scqo layer records
    that as a COUPLED readout_integration_s change). Shaped/optimized weights do
    not survive a length change (they are physically stale anyway): the rebuild
    is constant-window; integration_weights_angle applies on top and is untouched."""
    pulse = qubit.resonator.operations[operation]
    new_ns = _grid_ns(value, "readout_duration_s")
    window = _window_ns(pulse)  # read against the OLD length before changing it
    pulse.length = new_ns
    if window >= new_ns:
        _set_weights(pulse, DEFAULT_INTEGRATION_WEIGHTS_REF)
    else:
        _set_weights(pulse, [(1.0, window), (0.0, new_ns - window)])


def get_readout_integration(qubit: Any, operation: str = READOUT_OPERATION) -> float:
    """Integration window in seconds (nonzero-weight duration; see _window_ns).
    / 1e9, not * 1e-9 — see get_readout_duration."""
    return float(_window_ns(qubit.resonator.operations[operation])) / 1e9


def set_readout_integration(qubit: Any, value: float, *,
                            operation: str = READOUT_OPERATION) -> None:
    """Set the integration window (seconds) as zero-padded constant weights.

    [(1, w), (0, length - w)] spans the pulse exactly (the QUAM contract); the
    calibrated integration_weights_angle rotates whatever weights are set, so it
    survives untouched. A window equal to the pulse restores the default
    reference; a longer one is REFUSED — the QM demodulation cannot outlive the
    pulse, and the neutral field promises only what both backends realize."""
    pulse = qubit.resonator.operations[operation]
    length_ns = int(pulse.length)
    window = _grid_ns(value, "readout_integration_s")
    if window > length_ns:
        raise ValueError(
            f"readout_integration_s={value!r} s exceeds the readout pulse "
            f"({length_ns} ns): the integration weights cannot span past the "
            f"pulse - raise readout_duration_s first (or set both in one "
            f"command; the pulse pushes first)")
    if window == length_ns:
        _set_weights(pulse, DEFAULT_INTEGRATION_WEIGHTS_REF)
    else:
        _set_weights(pulse, [(1.0, window), (0.0, length_ns - window)])


# ------------------------------------------------------------------------ idle flux
def get_idle_flux(qubit: Any) -> float:
    """Standing z-line idle bias (V): the offset SELECTED by ``z.flux_point``
    (joint/independent/min/arbitrary; ``zero`` reads as 0.0). Which named point
    is active stays vendor config — the neutral knob is the bias AT that point."""
    z = qubit.z
    if z.flux_point == "zero":
        return 0.0
    return float(getattr(z, f"{z.flux_point}_offset"))


def set_idle_flux(qubit: Any, value: float) -> None:
    """Write the active flux point's offset (V). Applied to hardware by the next
    ``initialize_qpu`` (every probe runs it per batch), like any QUAM knob."""
    z = qubit.z
    if z.flux_point == "zero":
        raise ValueError(
            "z.flux_point='zero': the idle bias is fixed at 0 V - select "
            "joint/independent/min/arbitrary in the vendor config first")
    setattr(z, f"{z.flux_point}_offset", float(value))


# ------------------------------------------------------------------------- pi amplitude
def get_pi_amp(qubit: Any, operation: str = PI_OPERATION) -> float:
    return float(qubit.xy.operations[operation].amplitude)


def set_pi_amp(qubit: Any, value: float, *, operation: str = PI_OPERATION, lock_x90: bool = False) -> None:
    """Write the operation's amplitude; when ``operation`` is ``x180`` and ``lock_x90`` is
    set, lock ``x90`` to half the pi-pulse amplitude."""
    value = float(value)
    qubit.xy.operations[operation].amplitude = value
    if lock_x90 and operation == "x180":
        qubit.xy.operations["x90"].amplitude = value / 2
