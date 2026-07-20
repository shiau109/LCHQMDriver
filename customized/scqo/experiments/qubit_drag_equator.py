"""QM DRAG equator calibration for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitDragEquator``.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitDragEquator


@register
class QMQubitDragEquator(QubitDragEquator):
    """Build a multiplexed DRAG equator QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_drag_equator as equator_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)
        
        sweeps = self.define_sweep()
        beta_array = list(sweeps["beta"])

        return equator_probe.build_program(
            machine,
            qubits,
            num_shots=int(self.params.num_averages),
            beta_array=beta_array,
            pulse_repetitions=int(self.params.pulse_repetitions),
            use_state_discrimination=False,
        )
