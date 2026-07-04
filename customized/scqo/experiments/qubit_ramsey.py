"""QM Ramsey for scqo - supplies only ``probe()``.

Parameters, the decaying-cosine fit, T2*/detuning extraction and the drive_freq
writeback are all inherited from ``scqo.experiments.QubitRamsey``. This class only
compiles the scqo sweep into a QUA program via the shared LCHQM Ramsey probe.
"""

from __future__ import annotations

from typing import Any

import numpy as np
from scqo import register
from scqo.experiments import QubitRamsey


@register
class QMQubitRamsey(QubitRamsey):
    """Build a multiplexed Ramsey QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_ramsey as ramsey_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        # scqo sweeps idle time in ns; the QUA program sweeps in clock cycles (4 ns).
        idle_ns = self.sweep_axes["idle_time_ns"]
        idle_times_cycles = np.maximum(1, np.round(idle_ns / 4)).astype(int)

        return ramsey_probe.build_program(
            machine,
            qubits,
            idle_times_cycles=idle_times_cycles,
            detuning_hz=int(self.params.frequency_detuning_hz),
            num_shots=self.params.num_averages,
            reset_type="thermal",
            use_state_discrimination=False,
        )
