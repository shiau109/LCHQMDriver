"""Reset-check visualization: one overlay curve pair per measured qubit.

For each qubit the figure overlays the readout vs the swept x180 amplitude pre-factor for
reset="off" (baseline -> full Rabi oscillation) and reset="on" (the reset macro under test ->
should be flat near ground). With state discrimination the plotted variable is the
discriminated state (`state`, the excited-state population once averaged over shots);
without it the raw I quadrature is shown instead.
"""

from typing import Dict

import matplotlib.pyplot as plt
import xarray as xr


def plot_reset_check(ds_raw: xr.Dataset, measure_qubits, *, use_state_discrimination: bool) -> Dict[str, plt.Figure]:
    """Build one overlay (reset off vs on) figure per measured qubit; return {qubit_name: Figure}.

    The plotted variable is resolved from the dataset (so it works for both live and loaded
    data): `state` (excited-state population) when present, otherwise the raw `I` quadrature.
    `measure_qubits` is accepted for interface symmetry; the qubit names are taken from the
    dataset.
    """
    qubit_names = [str(q) for q in ds_raw.qubit.values]

    if "state" in ds_raw:
        var, ylabel = "state", "P(excited)"
    else:
        var, ylabel = "I", "I [V]"

    figures: Dict[str, plt.Figure] = {}
    for qubit in qubit_names:
        fig, ax = plt.subplots(figsize=(6, 4))
        ds_raw[var].sel(qubit=qubit, reset="off").plot(x="amp_prefactor", ax=ax, marker="o", label="no reset")
        ds_raw[var].sel(qubit=qubit, reset="on").plot(x="amp_prefactor", ax=ax, marker="o", label="with reset")
        ax.set_xlabel("x180 amplitude prefactor")
        ax.set_ylabel(ylabel)
        ax.set_title(f"Reset check - {qubit}")
        ax.legend()
        fig.tight_layout()
        figures[qubit] = fig

    return figures
