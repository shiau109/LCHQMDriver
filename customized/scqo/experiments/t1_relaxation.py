"""QM T1 relaxation for scqo - supplies only ``probe()``.

Parameters, exponential fit and reporting are inherited from
``scqo.experiments.T1Relaxation``. scqo sweeps ``wait_time_ns``; the LCHQM probe
builds the same sweep on coord ``idle_time``, which the backend's ``_to_canonical``
renames back.
"""

from __future__ import annotations

from typing import Any

import numpy as np

from scqo import register
from scqo.experiments import T1Relaxation


@register
class QMT1Relaxation(T1Relaxation):
    """Build a multiplexed T1 QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import t1_relaxation as t1_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        wait_ns = self.sweep_axes["wait_time_ns"]
        wait_cycles = np.maximum(1, np.round(wait_ns / 4)).astype(int)

        return t1_probe.build_program(
            machine,
            qubits,
            wait_times_cycles=wait_cycles,
            num_shots=self.params.num_averages,
            reset_type="thermal",
        )
