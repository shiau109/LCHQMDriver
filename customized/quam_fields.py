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
    drive_amp             <-> q.xy.operations['saturation'].amplitude
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
    """Write the pi-pulse amplitude.

    QUAM structure (state.json):
      - x180_DragCosine: the real pi-pulse storage node.
      - x90_DragCosine:  the real pi/2-pulse storage node.
      - x180, y180 etc.: QUAM reference aliases -> follow x180_DragCosine automatically.
      - -x90, y90, -y90: QUAM reference aliases -> follow x90_DragCosine automatically.

    So we write the DragCosine storage node directly (the plain ``x180`` alias is
    also written when it is a real pulse, for non-DragCosine setups). ``lock_x90``
    defaults False to preserve the historical power_rabi behaviour; when set, x90
    is locked to half the pi amplitude.
    """
    val = float(value)
    if not (hasattr(qubit, "xy") and hasattr(qubit.xy, "operations")):
        return
    ops = qubit.xy.operations
    # Write the REQUESTED operation's storage node. For the default x180 also write
    # the x180_DragCosine node (the plain "x180" is often a reference alias that
    # _set_op_amp skips); any other operation is written directly, so this respects
    # the `operation` contract the qualibrate writeback + power_rabi tests rely on.
    if operation == "x180":
        _set_op_amp(ops, "x180_DragCosine", val)
    _set_op_amp(ops, operation, val)
    # lock_x90 only ever couples x90 to HALF the x180 amplitude — never for other ops.
    if lock_x90 and operation == "x180":
        half_val = val / 2.0
        _set_op_amp(ops, "x90_DragCosine", half_val)
        _set_op_amp(ops, "x90", half_val)


def _set_op_amp(ops: Any, name: str, value: float) -> None:
    """Set ops[name].amplitude, but only when ops[name] is a real pulse object
    (not a plain QUAM string-reference alias)."""
    try:
        op = ops[name]
    except (KeyError, TypeError):
        return
    if isinstance(op, str):  # a string-reference entry -> skip (target holds the value)
        return
    if hasattr(op, "amplitude"):
        op.amplitude = value


# ------------------------------------------------------------------ saturation (spec) drive
#: The operation whose amplitude is the neutral ``drive_amp`` (the saturation /
#: spec drive played by qubit_spectroscopy; drive_power_dbm anchors to it).
SATURATION_OPERATION = "saturation"


def get_saturation_amp(qubit: Any, operation: str = SATURATION_OPERATION) -> float:
    return float(qubit.xy.operations[operation].amplitude)


def set_saturation_amp(qubit: Any, value: float, *, operation: str = SATURATION_OPERATION) -> None:
    """Write the saturation-pulse amplitude (within the current drive-chain
    config; the chain solve for an absolute power lives with drive_power_dbm in
    the scqo backend, next to the readout one)."""
    qubit.xy.operations[operation].amplitude = float(value)


# ------------------------------------------------------------------ DRAG coefficient
def get_drag_beta(qubit: Any, operation: str = PI_OPERATION) -> float:
    """Read the DRAG coefficient from the x180_DragCosine storage node (QUAM stores
    it as ``DragCosinePulse.alpha``); guards each access so one bad reference does
    not abort the search."""
    if not (hasattr(qubit, "xy") and hasattr(qubit.xy, "operations")):
        return 0.0
    ops = qubit.xy.operations
    for name in ("x180_DragCosine", operation):
        try:
            op = ops[name]
            if isinstance(op, str):
                continue
            alpha = op.alpha
            if alpha is not None:
                return float(alpha)
        except Exception:
            continue
    for name in list(ops):
        try:
            op = ops[name]
            if isinstance(op, str):
                continue
            alpha = op.alpha
            if alpha is not None:
                return float(alpha)
        except Exception:
            continue
    return 0.0


def set_drag_beta(qubit: Any, value: float, *, operation: str = PI_OPERATION, lock_x90: bool = True) -> None:
    """Write the DRAG coefficient (QUAM ``DragCosinePulse.alpha``) on the storage
    nodes; the reference aliases follow automatically."""
    val = float(value)
    if not (hasattr(qubit, "xy") and hasattr(qubit.xy, "operations")):
        return
    ops = qubit.xy.operations
    _set_op_alpha(ops, "x180_DragCosine", val)
    _set_op_alpha(ops, operation, val)
    if lock_x90:
        _set_op_alpha(ops, "x90_DragCosine", val)
        _set_op_alpha(ops, "x90", val)


def _set_op_alpha(ops: Any, name: str, value: float) -> None:
    """Set ops[name].alpha, skipping string-reference aliases."""
    try:
        op = ops[name]
    except (KeyError, TypeError):
        return
    if isinstance(op, str):
        return
    try:
        raw_alpha = op.__quam__.get("alpha") if hasattr(op, "__quam__") else None
        if isinstance(raw_alpha, str) and raw_alpha.startswith("#"):
            return
    except Exception:
        pass
    if hasattr(op, "alpha"):
        op.alpha = value
