"""QM resonator spectroscopy vs power for scqo - supplies only ``probe()``.

Parameters, the punchout analysis and the readout_amp/readout_freq writeback are
inherited from ``scqo.experiments.ResonatorSpectroscopyPower``. scqo sweeps
``(detuning_hz, power_db)``; the LCHQM probe builds the same sweep on coords
``(detuning, power)``, which the backend's ``_to_canonical`` renames positionally.

Power convention: scqo's ``power_db`` is relative dB (0 dB = current readout_amp);
the probe's ``amps`` prefactors scale the readout pulse per point
(``amplitude_scale``), so ``10**(power_db/20)`` maps exactly.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scqo import register
from scqo.experiments import ResonatorSpectroscopyPower


@register
class QMResonatorSpectroscopyPower(ResonatorSpectroscopyPower):
    """Build a multiplexed punchout QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import resonator_spectroscopy_power as power_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        power_db = self.sweep_axes["power_db"]
        return power_probe.build_program(
            machine,
            qubits,
            dfs=self.sweep_axes["detuning_hz"],
            amps=10.0 ** (np.asarray(power_db) / 20.0),
            power_dbm=power_db,  # relative-dB axis (0 = current readout_amp)
            num_shots=self.params.num_averages,
        )
