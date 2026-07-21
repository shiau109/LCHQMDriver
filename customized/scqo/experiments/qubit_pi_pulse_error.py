"""QM Pi-pulse error amplification for scqo - supplies only ``probe()``."""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitPiPulseError


@register
class QMQubitPiPulseError(QubitPiPulseError):
    """Build a multiplexed Pi-pulse error amplification QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_pi_pulse_error as pi_pulse_error_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        sweeps = self.define_sweep()
        amp_factors = list(sweeps["amp_factor"])
        gate_counts = list(sweeps["gate_count"])

        return pi_pulse_error_probe.build_program(
            machine,
            qubits,
            amp_factors=amp_factors,
            gate_counts=gate_counts,
            num_shots=int(self.params.num_averages),
            use_state_discrimination=False,
        )
