"""QM qubit power Rabi for scqo - supplies only ``probe()``.

Parameters, the cosine fit, opt_amp_prefactor extraction and the pi_amp writeback are
inherited from ``scqo.experiments.QubitPowerRabi``. scqo's ``amp_prefactor`` is already
a factor of the current pi pulse, which is exactly the LCHQM probe's
``amplitude_scale``, so the sweep passes straight through — and since the probe emits
that same axis NAME, ``_to_canonical`` matches it by name instead of by position.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitPowerRabi


@register
class QMQubitPowerRabi(QubitPowerRabi):
    """Build a multiplexed power-Rabi QUA program on the QM OPX."""

    def probe(self) -> Any:
        from ._reset import reset_type
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_power_rabi as power_rabi_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        return power_rabi_probe.build_program(
            machine,
            qubits,
            amps=self.sweep_axes["amp_prefactor"],
            operation="x180",
            num_shots=self.params.num_averages,
            reset_type=reset_type(self),
            use_state_discrimination=bool(self.params.use_state_discrimination),
            drive_qubit=None,
        )
