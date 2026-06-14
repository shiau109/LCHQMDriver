"""Power-Rabi update policy: pure fit -> amplitude decision + minimal QUAM writeback.

The shell decides *which* qubits to update (drive_qubit selection, failed
outcomes); this module decides *what* the new amplitude is and writes it.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class PowerRabiUpdate:
    opt_amp: float  # new pulse amplitude for the swept operation


def compute_update(fit: Dict, current_amplitude: float) -> PowerRabiUpdate:
    """Pure decision: scale the current pulse amplitude by the fitted prefactor."""
    return PowerRabiUpdate(opt_amp=fit["opt_amp_prefactor"] * current_amplitude)


def apply_update(qubit, operation: str, upd: PowerRabiUpdate, *, update_x90: bool) -> None:
    """Write the calibrated amplitude onto the QUAM qubit (call inside the
    shell's `record_state_updates()` when GUI approval is wanted).

    When the swept operation is x180 and `update_x90` is set, x90 is locked to
    half the pi-pulse amplitude.
    """
    qubit.xy.operations[operation].amplitude = upd.opt_amp
    if operation == "x180" and update_x90:
        qubit.xy.operations["x90"].amplitude = upd.opt_amp / 2
