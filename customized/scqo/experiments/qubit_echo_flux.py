"""QM Hahn echo vs flux for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitEchoFlux``.
"""

from __future__ import annotations

from typing import Any
import numpy as np

from scqo import register
from scqo.experiments import QubitEchoFlux


@register
class QMQubitEchoFlux(QubitEchoFlux):
    """Build a multiplexed Hahn echo vs flux QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_echo_flux as echo_flux_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)
        
        sweeps = self.define_sweep()
        wait_times_ns = sweeps["wait_time_ns"]
        # wait_time_ns is the total echo delay (8 * idle_time_cycles in ns)
        # So wait_time_ns = 8 * idle_times_cycles -> idle_times_cycles = wait_time_ns / 8
        idle_times_cycles = [int(round(t / 8.0)) for t in wait_times_ns]
        flux_amp_array = list(sweeps["flux_amp"])

        return echo_flux_probe.build_program(
            machine,
            qubits,
            num_shots=int(self.params.num_averages),
            idle_times_cycles=idle_times_cycles,
            flux_amp_array=flux_amp_array,
            use_state_discrimination=bool(self.params.use_state_discrimination),
        )
