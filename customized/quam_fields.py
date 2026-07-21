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
    readout_freq  <-> q.resonator.RF_frequency  (and q.resonator.f_01 when present)
    drive_freq    <-> q.f_01                     (and q.xy.RF_frequency, kept in step)
    pi_amp        <-> q.xy.operations['x180'].amplitude
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


# ------------------------------------------------------------------------- pi amplitude
def get_pi_amp(qubit: Any, operation: str = PI_OPERATION) -> float:
    return float(qubit.xy.operations[operation].amplitude)


def set_pi_amp(qubit: Any, value: float, *, operation: str = PI_OPERATION, lock_x90: bool = True) -> None:
    """Write the pi-pulse amplitude.

    QUAM structure (state.json):
      - x180_DragCosine: the real pi-pulse storage node.
      - x90_DragCosine:  the real pi/2-pulse storage node.
      - x180, y180 etc.: QUAM reference aliases → follow x180_DragCosine automatically.
      - -x90, y90, -y90: QUAM reference aliases → follow x90_DragCosine automatically.

    So we only need to write x180_DragCosine and (when lock_x90=True) x90_DragCosine.
    """
    val = float(value)
    if not (hasattr(qubit, "xy") and hasattr(qubit.xy, "operations")):
        return
    ops = qubit.xy.operations

    # --- pi pulse: update the real storage node (x180_DragCosine) directly ---
    # Also try "x180" in case the setup uses a plain SquarePulse alias.
    _set_op_amp(ops, "x180_DragCosine", val)
    _set_op_amp(ops, "x180", val)

    # --- pi/2 pulse: update x90_DragCosine (and plain x90 alias if present) ---
    if lock_x90:
        half_val = val / 2.0
        _set_op_amp(ops, "x90_DragCosine", half_val)
        _set_op_amp(ops, "x90", half_val)


def _set_op_amp(ops: Any, name: str, value: float) -> None:
    """Set ops[name].amplitude = value, but only when ops[name] is a real
    pulse object (not a plain QUAM string-reference alias)."""
    try:
        op = ops[name]
    except (KeyError, TypeError):
        return
    # If QUAM resolved the reference to a string it means this entry is itself
    # a string-reference (e.g. '"#./x180_DragCosine"') — skip it so we don't
    # overwrite the actual storage node twice or corrupt the reference.
    if isinstance(op, str):
        return
    if hasattr(op, "amplitude"):
        op.amplitude = value


# ------------------------------------------------------------------------- DRAG beta / alpha
def get_drag_beta(qubit: Any, operation: str = PI_OPERATION) -> float:
    """Return the DRAG alpha, reading from x180_DragCosine (the storage node) first.

    QUAM reference entries like "x180: #./x180_DragCosine" can throw KeyError
    during resolution; we guard each access individually so a single bad reference
    does not abort the entire search.
    """
    if not (hasattr(qubit, "xy") and hasattr(qubit.xy, "operations")):
        return 0.0
    ops = qubit.xy.operations

    # 1) Try the canonical DragCosine storage node first (avoids reference resolution).
    for name in ("x180_DragCosine", operation):
        try:
            op = ops[name]
            if isinstance(op, str):
                continue  # it IS a reference alias — its alpha is on the target
            alpha = op.alpha
            if alpha is not None:
                return float(alpha)
        except Exception:
            continue

    # 2) Fallback: iterate all operations, guarding each individually.
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



