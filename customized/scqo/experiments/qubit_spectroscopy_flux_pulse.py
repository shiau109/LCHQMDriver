"""QM qubit spectroscopy vs PULSED flux for scqo - supplies only ``probe()``.

Parameters, the transmon-arch fit and reporting are inherited from
``scqo.experiments.QubitSpectroscopyFluxPulse``. scqo sweeps ``(flux_bias_v,
detuning_hz)``; the LCHQM probe sweeps ``dcs`` (flux, V) and ``dfs`` (drive
detuning, Hz) with each qubit fluxing/driving its OWN lines (z/xy source = None,
as in the official 03b node).

PULSE CONTRACT: this probe conforms to the ``_pulse`` name by construction — the
flux is a z PULSE played only alongside the saturation drive
(``customized/probes/qubit_spectroscopy_flux.py``: ``qubit.z.play(...,
duration=operation_duration)`` then ``align()`` then ``measure``), so every
readout happens at idle flux and the neutral ``estimate()`` reduces the map
against ONE global IQ reference. The probe MODULE keeps its historical name (it
is shared with the qualibrate shell path).

AXIS-ORDER NOTE (do not "fix" the order below): the probe's QUA loops nest df
(outer) over dc (inner) and its streams are ``buffer(len(dcs)).buffer(len(dfs))``,
so the raw per-qubit array is shaped (detuning, flux) — the OPPOSITE of scqo's
declared sweep order (flux_bias_v, detuning_hz). A positional rename in
``_to_canonical`` would therefore swap the axes (silently, whenever the two sweep
lengths happen to be equal). Instead we re-key the probe's sweep_axes with the
canonical scqo names IN RAW NESTING ORDER; ``_to_canonical`` then takes its
name-based path (no rename, per-name size checks) and ``estimate()`` transposes
by name.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import QubitSpectroscopyFluxPulse


@register
class QMQubitSpectroscopyFluxPulse(QubitSpectroscopyFluxPulse):
    """Build a multiplexed 2D (pulsed-flux x detuning) spectroscopy QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import qubit_spectroscopy_flux as flux_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        prog, axes = flux_probe.build_program(
            machine,
            qubits,
            dfs=self.sweep_axes["detuning_hz"],
            dcs=self.sweep_axes["flux_bias_v"],
            operation="saturation",
            operation_len=None,  # use each qubit's own saturation-pulse length
            operation_amp=1.0,
            num_shots=self.params.num_averages,
            # None = every measured qubit fluxes its own z line; a QUBIT name is
            # the assigned single source (scqo validated it — this probe plays z
            # pulses, so a pair's coupler is not sweepable here).
            z_source_qubit=self.params.flux_component,
            xy_source_qubit=None,  # None = every measured qubit drives its own xy line
        )
        # Canonical names in RAW nesting order (detuning outer, flux inner — see
        # module docstring); the DataArray values (incl. units attrs) are reused.
        sweep_axes = {
            "qubit": axes["qubit"],
            "detuning_hz": axes["detuning"],
            "flux_bias_v": axes["flux_bias"],
        }
        return prog, sweep_axes
