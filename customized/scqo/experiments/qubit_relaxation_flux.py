"""QM qubit relaxation vs flux (T1 spectrum) for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitRelaxationFlux``.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scqo import register
from scqo.experiments import QubitRelaxationFlux


@register
class QMQubitRelaxationFlux(QubitRelaxationFlux):
    """Build a multiplexed T1 vs Flux QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_relaxation_flux as t1_flux_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        sweeps = self.define_sweep()
        flux_amp = list(sweeps["flux_amp"])
        wait_ns = sweeps["wait_time_ns"]
        wait_cycles = np.maximum(1, np.round(wait_ns / 4)).astype(int)

        return t1_flux_probe.build_program(
            machine,
            qubits,
            wait_times_cycles=wait_cycles,
            flux_amps_v=flux_amp,
            num_shots=int(self.params.num_averages),
            reset_type="thermal",
        )
