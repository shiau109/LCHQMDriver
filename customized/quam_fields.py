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


def set_pi_amp(qubit: Any, value: float, *, operation: str = PI_OPERATION, lock_x90: bool = False) -> None:
    """Write the operation's amplitude; when ``operation`` is ``x180`` and ``lock_x90`` is
    set, lock ``x90`` to half the pi-pulse amplitude."""
    value = float(value)
    qubit.xy.operations[operation].amplitude = value
    if lock_x90 and operation == "x180":
        qubit.xy.operations["x90"].amplitude = value / 2
