"""N-swap (swap-chain) visualization: one 1D curve per measured qubit.

With state discrimination the probe saves the discriminated state (var `state`, the
excited-state population once averaged over shots); each measured qubit gets a line plot
of population vs N. Without state discrimination the raw I quadrature is shown instead.
"""

from typing import Dict

import matplotlib.pyplot as plt
import xarray as xr


def plot_rounds_1d(ds_raw: xr.Dataset, measure_qubits, *, use_state_discrimination: bool) -> Dict[str, plt.Figure]:
    """Build one population-vs-N figure per measured qubit; return {qubit_name: Figure}.

    The plotted variable is resolved from the dataset (so it works for both live and
    loaded data): `state` (excited-state population) when present, otherwise the raw `I`
    quadrature. `measure_qubits` is accepted for interface symmetry; the qubit names are
    taken from the dataset.
    """
    qubit_names = [str(q) for q in ds_raw.qubit.values]

    if "state" in ds_raw:
        var, ylabel = "state", "P(excited)"
    else:
        var, ylabel = "I", "I [V]"

    figures: Dict[str, plt.Figure] = {}
    for qubit in qubit_names:
        fig, ax = plt.subplots(figsize=(6, 4))
        ds_raw[var].sel(qubit=qubit).plot(x="round", ax=ax, marker="o")
        ax.set_xlabel("Number of swaps N")
        ax.set_ylabel(ylabel)
        ax.set_title(f"N-swap - {qubit}")
        fig.tight_layout()
        figures[qubit] = fig

    return figures
