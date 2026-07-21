"""QM SQRB for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitSQRB``.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitSQRB


@register
class QMQubitSQRB(QubitSQRB):
    """Build a multiplexed SQRB QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_sqrb as sqrb_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        depths = self.params.get_depths()

        return sqrb_probe.build_program(
            machine,
            qubits,
            depths=depths,
            num_sequences=int(self.params.num_random_sequences),
            num_shots=int(self.params.num_averages),
            use_state_discrimination=bool(self.params.use_state_discrimination),
            seed=self.params.seed,
        )
