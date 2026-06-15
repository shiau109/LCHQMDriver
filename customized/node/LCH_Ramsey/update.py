"""Ramsey update policy: pure fit -> correction decision + minimal QUAM writeback.

Branches on the estimator's authoritative `model_type`:
  * beat       -> mean of (f_1, f_2) calibrates the qubit; the half-split is
                  recorded as charge dispersion;
  * single     -> f_1 calibrates the qubit;
  * relaxation -> f_1 is reported as 0 (fringe unresolvable), so the
                  single-frequency path applies a -detuning correction.
"""

from dataclasses import dataclass
from typing import Dict


@dataclass(frozen=True)
class RamseyUpdate:
    d_f01: int               # Hz; subtracted from q.f_01 and q.xy.RF_frequency
    charge_dispersion: int   # Hz; written to q.charge_dispersion


def compute_update(fit: Dict, detuning_hz: int) -> RamseyUpdate:
    """Pure decision: scqat fit metadata (frequencies in GHz) -> RamseyUpdate."""
    f_1 = float(fit["f_1"]) * 1e9
    if fit.get("model_type") == "beat":
        f_2 = float(fit["f_2"]) * 1e9
        return RamseyUpdate(
            d_f01=int((f_1 + f_2) / 2) - detuning_hz,
            charge_dispersion=int(abs(f_1 - f_2) / 2),
        )
    return RamseyUpdate(d_f01=int(f_1) - detuning_hz, charge_dispersion=0)


def apply_update(qubit, upd: RamseyUpdate) -> None:
    """Write the correction onto the QUAM qubit (call inside the shell's
    `record_state_updates()` when GUI approval is wanted)."""
    qubit.f_01 -= upd.d_f01
    qubit.xy.RF_frequency -= upd.d_f01
    qubit.charge_dispersion = upd.charge_dispersion
