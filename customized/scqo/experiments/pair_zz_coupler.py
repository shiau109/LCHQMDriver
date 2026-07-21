"""QM residual-ZZ vs coupler bias for scqo - supplies ``probe()`` + the raw
joint-state reduction.

Parameters, the per-bias echo-fringe fit and the coupler_decouple_v/zz_hz
writeback are inherited from ``scqo.experiments.PairZZCoupler``. scqo sweeps
``(coupler_bias_v, idle_time_ns)``; the LCHQM probe sweeps ``amplitudes`` (V on
the pair's tunable coupler) x ``durations`` (interaction time, clock cycles) with
a Hahn echo + virtual detuning on ONE pair member and joint two-qubit state
readout. The neutral ``measure`` role (high/low, roster-declared) is mapped onto
the vendor's control/target here; ``reduce_raw`` turns the joint populations into
the canonical ``signal`` (the measured qubit's excited-state probability).
"""

from __future__ import annotations

from typing import Any

import numpy as np
import xarray as xr
from scqo import register
from scqo.experiments import PairZZCoupler


@register
class QMPairZZCoupler(PairZZCoupler):
    """Build the multiplexed ZZ-vs-coupler QUA program on the QM OPX (QCQ pairs)."""

    def _measure_side(self, machine: Any) -> str:
        """Map the neutral ``measure`` role (high/low) onto vendor control/target.

        The roster's declared high/low members are the governed truth; without a
        roster (standalone backend use) the live f_01s decide. The probe takes ONE
        side for all pairs, so a mixed mapping across the selected pairs refuses."""
        roster = getattr(self.device, "roster", None)
        sides: dict[str, str] = {}
        for pair_name in self.params.targets:
            qp = machine.qubit_pairs[pair_name]
            control = qp.qubit_control.name
            target = qp.qubit_target.name
            if roster is not None:
                measured = roster.members(pair_name)[self.params.measure]
            else:  # standalone fallback: high = larger live f_01
                f_c = float(qp.qubit_control.f_01 or 0)
                f_t = float(qp.qubit_target.f_01 or 0)
                high = control if f_c >= f_t else target
                low = target if high == control else control
                measured = high if self.params.measure == "high" else low
            if measured == control:
                sides[pair_name] = "control"
            elif measured == target:
                sides[pair_name] = "target"
            else:
                raise ValueError(
                    f"{pair_name}: roster member {self.params.measure}={measured!r} "
                    f"is neither the vendor pair's control ({control}) nor target "
                    f"({target}) - roster/vendor naming mismatch")
        if len(set(sides.values())) > 1:
            raise ValueError(
                f"measure={self.params.measure!r} maps onto DIFFERENT vendor sides "
                f"across the selected pairs ({sides}); the probe measures one side "
                f"per program - run these pairs in separate commands")
        return next(iter(sides.values()))

    def probe(self) -> Any:
        from customized.probes import pair_qcq_zz_coupler_freq as zz_probe
        from customized.probes._lib import select_qubit_pairs

        machine = self.backend.machine  # type: ignore[attr-defined]
        pairs = select_qubit_pairs(machine, self.params.targets, multiplexed=True)
        self._side = self._measure_side(machine)

        # Canonical idle times (ns) -> clock cycles; the raw time axis is the
        # QUANTIZED grid (durations*4 ns), which estimate() reads from coords.
        cycles = np.unique(np.clip(
            np.round(self.sweep_axes["idle_time_ns"] / 4).astype(int), 4, None))
        amplitudes = self.sweep_axes["coupler_bias_v"]

        prog, axes = zz_probe.build_program(
            machine,
            pairs,
            amplitudes=amplitudes,
            durations=cycles,
            detuning_hz=int(self.params.detuning_hz),
            num_shots=self.params.num_averages,
            reset_type="thermal",
            use_state_discrimination=True,
            measure_qubit=self._side,
        )
        # The canonical time axis is the probe's REAL quantized grid: re-declare
        # it so sizes and values match the raw data exactly.
        self.sweep_axes["idle_time_ns"] = axes["time"].values.astype(float)
        sweep_axes = {
            "qubit_pair": axes["qubit_pair"],
            "coupler_bias_v": axes["amp"],
            "idle_time_ns": axes["time"],
        }
        return prog, sweep_axes

    def reduce_raw(self, raw: xr.Dataset) -> xr.Dataset:
        """Joint two-qubit populations -> the measured qubit's excited-state
        probability (the canonical ``signal``). First digit = control."""
        if "state_ee" in raw.data_vars:
            sig = (raw["state_eg"] + raw["state_ee"] if self._side == "control"
                   else raw["state_ge"] + raw["state_ee"])
        else:  # IQ fallback (no state discrimination): fit the I fringe
            sig = raw["I_control"] if self._side == "control" else raw["I_target"]
        return sig.to_dataset(name="signal")
