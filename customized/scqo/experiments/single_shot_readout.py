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

import numpy as np

from scqo import Outcome, register
from scqo.experiments import SingleShotReadout


@register
class QMSingleShotReadout(SingleShotReadout):
    """Build a multiplexed per-shot |g>/|e> readout QUA program on the QM OPX, and
    (opt-in) recalibrate the QM readout discriminator from the measured blobs."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import readout_fidelity as fidelity_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        return fidelity_probe.build_program(
            machine,
            qubits,
            operation="readout",
            num_shots=self.params.num_shots,
            reset_type="thermal",
        )

    def update(self) -> None:
        """Governed readout_fidelity write (inherited) + the OPT-IN vendor discriminator
        calibration.

        When ``calibrate_discriminator`` is set, this writes the QM readout operation's
        ``integration_weights_angle`` / ``threshold`` / ``rus_exit_threshold`` and SAVES
        the QUAM config IMMEDIATELY -- an out-of-band vendor calibration, like running
        the qualibrate ``07_iq_blobs`` node, NOT a governed suggestion. It runs whenever
        ``update()`` runs (i.e. under both update='suggest' and 'apply'); update='none'
        skips it. ``self.device.save()`` only fires on apply/accept, so the driver calls
        ``machine.save()`` itself to persist into the setup's ``backend_config/state.json``.
        """
        super().update()  # the governed readout_fidelity suggestion (through self.device)

        if not self.params.calibrate_discriminator or self.result is None or self.dataset is None:
            return
        from customized.scqo.discriminator import compute_qm_discriminator

        machine = self.backend.machine  # type: ignore[attr-defined]
        wrote = False
        for qubit in self.params.targets:
            if self.result.outcomes.get(qubit) is not Outcome.SUCCESSFUL:
                continue
            fit = self.result.fit[qubit]
            mean_g = (fit["mean_g_i"], fit["mean_g_q"])
            mean_e = (fit["mean_e_i"], fit["mean_e_q"])
            if not np.all(np.isfinite([*mean_g, *mean_e])):
                print(f"[single_shot_readout] {qubit}: degenerate blobs; discriminator not calibrated")
                continue

            sq = self.dataset.sel(target=qubit)
            shots_g = (sq["I"].sel(prepared_state=0).values, sq["Q"].sel(prepared_state=0).values)
            shots_e = (sq["I"].sel(prepared_state=1).values, sq["Q"].sel(prepared_state=1).values)
            d = compute_qm_discriminator(mean_g, mean_e, shots_g, shots_e)

            op = machine.qubits[qubit].resonator.operations["readout"]
            old_angle = float(op.integration_weights_angle)
            op.integration_weights_angle = old_angle - d["delta_angle_rad"]  # 07's accumulate (-=)
            op.threshold = d["ge_threshold"]
            op.rus_exit_threshold = d["rus_exit_threshold"]
            wrote = True
            print(
                f"[single_shot_readout] {qubit}: discriminator calibrated "
                f"(integration_weights_angle {old_angle:.4f} -> "
                f"{op.integration_weights_angle:.4f} rad, threshold {op.threshold:.4g})"
            )

        if wrote:
            machine.save()  # persist the vendor calibration to backend_config/state.json
            print("[single_shot_readout] saved QUAM discriminator calibration")
