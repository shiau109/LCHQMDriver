"""QM DRAG alternating calibration for scqo - supplies only ``probe()``.

Parameters, fit, and reporting are inherited from ``scqo.experiments.QubitDragAlternating``.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitDragAlternating


@register
class QMQubitDragAlternating(QubitDragAlternating):
    """Build a multiplexed DRAG alternating QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_drag_alternating as alternating_probe

        machine = self.backend.machine
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)
        
        sweeps = self.define_sweep()
        beta_array = list(sweeps["beta"])
        nb_pulses_array = [int(x) for x in sweeps["nb_of_pulses"]]

        use_hw_disc = getattr(self.params, "readout_mode", "raw_iq") == "hardware_state"
        return alternating_probe.build_program(
            machine,
            qubits,
            num_shots=int(self.params.num_averages),
            beta_array=beta_array,
            nb_pulses_array=nb_pulses_array,
            use_state_discrimination=use_hw_disc,
        )
