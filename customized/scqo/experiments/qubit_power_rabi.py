"""QM qubit power Rabi for scqo - supplies only ``probe()``.

Parameters, the cosine fit, pi_amp_factor extraction and the pi_amp writeback are
inherited from ``scqo.experiments.QubitPowerRabi``. scqo's ``amp_factor`` is already a
factor of the current pi pulse, which is exactly the LCHQM probe's
``amplitude_scale``, so the sweep passes straight through.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitPowerRabi


@register
class QMQubitPowerRabi(QubitPowerRabi):
    """Build a multiplexed power-Rabi QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_power_rabi as power_rabi_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        return power_rabi_probe.build_program(
            machine,
            qubits,
            amps=self.sweep_axes["amp_factor"],
            operation="x180",
            num_shots=self.params.num_averages,
            reset_type="thermal",
            use_state_discrimination=False,
            drive_qubit=None,
        )
