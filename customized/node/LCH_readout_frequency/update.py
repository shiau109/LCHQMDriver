"""Readout-frequency update policy: pure fit -> detuning decision + minimal QUAM writeback.

The sweep spans a detuning around the current readout IF, so the optimal
detuning is added onto the resonator RF frequency. Success gating stays in the
shell (it owns `node.outcomes`).
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class ReadoutFreqUpdate:
    detuning: float  # Hz; added to q.resonator.RF_frequency


def compute_update(fit: Dict) -> ReadoutFreqUpdate:
    """Pure decision: the estimator's best detuning is the frequency shift."""
    return ReadoutFreqUpdate(detuning=float(fit["best_detuning"]))


def apply_update(qubit, upd: ReadoutFreqUpdate) -> None:
    """Shift the readout frequency (call inside the shell's
    `record_state_updates()` when GUI approval is wanted)."""
    qubit.resonator.RF_frequency = float(qubit.resonator.RF_frequency + upd.detuning)
