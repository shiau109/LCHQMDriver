"""QM single-shot readout fidelity for scqo - supplies only ``probe()``.

Parameters, the two-Gaussian-mixture fit and reporting are inherited from
``scqo.experiments.SingleShotReadout``. PER-SHOT contract: every readout shot's
I/Q point is recorded individually — the probe's streams are
``buffer(2).buffer(num_shots)`` with NO ``.average()``.

AXIS-ORDER NOTE: the probe's QUA loops nest the shot loop (outer) over the
prepared-state loop (inner), so the raw per-qubit array is shaped
(shot_idx, prepared_state) — the OPPOSITE of scqo's declared sweep order
(prepared_state, shot_idx). The probe's sweep_axes already carry the canonical
names ``shot_idx``/``prepared_state`` in that raw nesting order, so the backend's
``_to_canonical`` takes its name-based path (no positional rename — which would
try to swap the axes) and ``estimate()`` transposes by name.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import SingleShotReadout


@register
class QMSingleShotReadout(SingleShotReadout):
    """Build a multiplexed per-shot |g>/|e> readout QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import readout_fidelity as fidelity_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.qubits, multiplexed=True)

        return fidelity_probe.build_program(
            machine,
            qubits,
            operation="readout",
            num_shots=self.params.num_shots,
            reset_type="thermal",
        )
