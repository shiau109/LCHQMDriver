"""QM qubit echo vs flux (T2 echo spectrum) for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitEchoFlux``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scqo import register
from scqo.experiments import QubitEchoFlux


@register
class QMQubitEchoFlux(QubitEchoFlux):
    """Build a multiplexed T2 Echo vs Flux QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_echo_flux as echo_flux_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        sweeps = self.define_sweep()
        flux_amp = list(sweeps["flux_amp"])
        wait_ns = sweeps["wait_time_ns"]
        wait_cycles = np.maximum(1, np.round((wait_ns / 2) / 4)).astype(int)

        return echo_flux_probe.build_program(
            machine,
            qubits,
            wait_times_cycles=wait_cycles,
            flux_amps_v=flux_amp,
            num_shots=int(self.params.num_averages),
            reset_type="thermal",
        )
