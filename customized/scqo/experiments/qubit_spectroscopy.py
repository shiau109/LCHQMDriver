"""QM qubit spectroscopy for scqo - supplies only ``probe()``.

Parameters, peak fitting and the drive_freq writeback are inherited from
``scqo.experiments.QubitSpectroscopy``. scqo sweeps ``detuning_hz``; the LCHQM probe
builds the same sweep on coord ``detuning``, which the backend's ``_to_canonical``
renames back.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitSpectroscopy


@register
class QMQubitSpectroscopy(QubitSpectroscopy):
    """Build a multiplexed two-tone spectroscopy QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_spectroscopy as spec_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        return spec_probe.build_program(
            machine,
            qubits,
            dfs=self.sweep_axes["detuning_hz"],
            operation="saturation",
            operation_len=int(self.params.drive_len_ns) if self.params.drive_len_ns else None,
            operation_amp=self.params.drive_amp,
            num_shots=self.params.num_averages,
            reset_type="thermal",
        )
