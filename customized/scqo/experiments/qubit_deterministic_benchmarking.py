"""QM Deterministic Benchmarking for scqo - supplies only ``probe()``."""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitDeterministicBenchmarking


@register
class QMQubitDeterministicBenchmarking(QubitDeterministicBenchmarking):
    """Build a multiplexed Deterministic Benchmarking QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_deterministic_benchmarking as db_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)
        repetitions = self.params.get_repetitions()

        return db_probe.build_program(
            machine,
            qubits,
            num_shots=int(self.params.num_averages),
            repetitions=repetitions,
            amp_factors=self.params.get_amp_factors(),
            target_gate=self.params.target_gate,
            use_state_discrimination=self.params.use_state_discrimination,
        )


