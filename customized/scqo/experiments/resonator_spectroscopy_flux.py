"""QM resonator spectroscopy vs flux for scqo - supplies only ``probe()``.

Parameters, the dispersive-model fit and reporting are inherited from
``scqo.experiments.ResonatorSpectroscopyFlux``. scqo sweeps ``(flux_bias_v,
detuning_hz)``; the LCHQM probe sweeps ``dcs`` (flux, V) and ``dfs`` (readout
detuning, Hz, relative to each resonator's current IF — same convention as the
resonator_spectroscopy wrapper) with each qubit fluxing its OWN z line
(z_source=None, as in the official 02c node).

AXIS-ORDER NOTE (do not "simplify" the re-key below): the probe's QUA loops nest
dc (outer) over df (inner) and its streams are
``buffer(num_shots).map(average()).buffer(len(dfs)).buffer(len(dcs))``, so the raw
per-qubit array is shaped (flux, detuning) — which for THIS probe happens to match
scqo's declared sweep order (flux_bias_v, detuning_hz). We still re-key the
probe's sweep_axes with the canonical scqo names IN RAW NESTING ORDER so the
backend's ``_to_canonical`` takes its name-based path (per-name size checks, no
rename): a positional rename would silently swap equal-sized axes if either
nesting ever changed, while the name-based path stays correct because
``estimate()`` transposes by name.
"""

from __future__ import annotations

from typing import Any

from scqo import register
from scqo.experiments import ResonatorSpectroscopyFlux


@register
class QMResonatorSpectroscopyFlux(ResonatorSpectroscopyFlux):
    """Build a multiplexed 2D (flux x detuning) resonator-spectroscopy QUA program on the QM OPX."""

    def probe(self) -> Any:
        from customized.probes._lib import select_qubits
        from customized.probes import resonator_spectroscopy_flux as flux_probe

        machine = self.backend.machine  # type: ignore[attr-defined]
        qubits = select_qubits(machine, self.params.targets, multiplexed=True)

        prog, axes = flux_probe.build_program(
            machine,
            qubits,
            dcs=self.sweep_axes["flux_bias_v"],
            dfs=self.sweep_axes["detuning_hz"],
            num_shots=self.params.num_averages,
            # None = every measured qubit fluxes its own z line; a component name
            # (qubit -> its z, pair -> its tunable coupler) is the assigned
            # single source (scqo validated it against the roster pre-probe).
            z_source=self.params.flux_component,
        )
        # Canonical names in RAW nesting order (flux outer, detuning inner — see
        # module docstring); the DataArray values (incl. units attrs) are reused.
        sweep_axes = {
            "qubit": axes["qubit"],
            "flux_bias_v": axes["flux_bias"],
            "detuning_hz": axes["detuning"],
        }
        return prog, sweep_axes
