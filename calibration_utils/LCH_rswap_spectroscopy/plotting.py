
from typing import List
import xarray as xr
from matplotlib.axes import Axes
from matplotlib.figure import Figure

from qualang_tools.units import unit
from qualibration_libs.plotting import QubitGrid, grid_iter
from qualibration_libs.analysis import lorentzian_peak
from quam_builder.architecture.superconducting.qubit import AnyTransmon

u = unit(coerce_to_integer=True)

# Plot I or state vs full_freq for each qubit, each in its own figure
def plot_qubit_lineplots(ds):
    """
    For each qubit in ds, plot I (or state) vs full_freq in its own figure.
    Returns a list of figures.
    """
    import matplotlib.pyplot as plt
    figs = []
    qubits = ds.coords["qubit"].values if "qubit" in ds.coords else ds["qubit"].values
    for q in qubits:
        fig, ax = plt.subplots()
        dssel = ds.sel(qubit=q)
        x = dssel["full_freq"].values
        if "I" in dssel:
            y = dssel["I"].values
            ax.plot(x, y, marker="o")
            ax.set_ylabel("I")
        elif "state" in dssel:
            y = dssel["state"].values
            ax.plot(x, y, marker="o")
            ax.set_ylabel("state")
        else:
            continue
        ax.set_xlabel("full_freq")
        ax.set_title(f"Qubit {q}")
        ax.grid(True)
        figs.append(fig)
    return figs



if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    import matplotlib.pyplot as plt
    ds = load_xarray_h5(r"data/QPU_project/2025-09-01/#1357_LCH_rswap_spectroscopy_150217/ds_raw.h5")
    print(ds)
    plot_qubit_lineplots(ds)
    plt.show()

