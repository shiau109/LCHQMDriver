from typing import List
import xarray as xr
from matplotlib.axes import Axes

from qualang_tools.units import unit
from qualibration_libs.plotting import QubitGrid, grid_iter
from qualibration_libs.analysis import decay_exp
from quam_builder.architecture.superconducting.qubit import AnyTransmon

u = unit(coerce_to_integer=True)


def plot_raw_data_with_fit(ds: xr.Dataset, qubits: List[AnyTransmon], fits: xr.Dataset=None):
    """
    Plots the resonator spectroscopy amplitude IQ_abs with fitted curves for the given qubits.

    Parameters
    ----------
    ds : xr.Dataset
        The dataset containing the quadrature data.
    qubits : list of AnyTransmon
        A list of qubits to plot.
    fits : xr.Dataset
        The dataset containing the fit parameters.

    Returns
    -------
    Figure
        The matplotlib figure object containing the plots.

    Notes
    -----
    - The function creates a grid of subplots, one for each qubit.
    - Each subplot contains the raw data and the fitted curve.
    """
    grid = QubitGrid(ds, [q.grid_location for q in qubits])
    for ax, qubit in grid_iter(grid):
        q_label = qubit["qubit"]
        plot_ds = ds.sel(qubit=qubit["qubit"])
        plot_individual_data_with_fit(ax, plot_ds, q_label)

    grid.fig.suptitle("ZZ interation with Coupler Offset")
    grid.fig.set_size_inches(15, 9)
    grid.fig.tight_layout()
    return grid.fig


def plot_individual_data_with_fit(ax: Axes, ds: xr.Dataset, q_label: str, fit: xr.Dataset = None):
    """
    Plots individual qubit data on a given axis with optional fit.

    Parameters
    ----------
    ax : matplotlib.axes.Axes
        The axis on which to plot the data.
    ds : xr.Dataset
        The dataset containing the quadrature data.
    qubit : dict[str, str]
        mapping to the qubit to plot.
    fit : xr.Dataset, optional
        The dataset containing the fit parameters (default is None).

    Notes
    -----
    - If the fit dataset is provided, the fitted curve is plotted along with the raw data.
    """

    # Select data for the specific qubit
    qubit_data = ds

    # Prefer 'state' variable for a 2D heatmap; fall back to 'I' quadrature
    var_to_plot = None
    cmap = "viridis"
    if "state" in qubit_data.data_vars:
        var_to_plot = qubit_data["state"]
        cmap = "viridis"
    elif "I" in qubit_data.data_vars:
        var_to_plot = qubit_data["I"]
        cmap = "RdBu_r"
    else:
        raise RuntimeError("The dataset must contain either 'state' or 'I' to plot a 2D heatmap.")

    # If ctrl_switch coordinate exists, prefer ctrl_switch=True slice for plotting
    if "ctrl_switch" in var_to_plot.coords:
        try:
            var_plot = var_to_plot.sel(ctrl_switch=True)
        except Exception:
            var_plot = var_to_plot.mean(dim="ctrl_switch")
    else:
        var_plot = var_to_plot

    # Plot 2D heatmap if dims exist
    if "qubit_amp" in var_plot.dims and "coupler_amp" in var_plot.dims:
        var_plot.plot(
            ax=ax,
            x="qubit_amp",
            y="coupler_amp",
            add_colorbar=True,
            cmap=cmap
        )
    else:
        # If dims are not present, fallback to a simple line plot over existing dims
        try:
            flat = var_plot.squeeze()
            flat.plot(ax=ax)
        except Exception:
            ax.text(0.5, 0.5, "No plottable 2D dims found", ha="center")

    ax.set_ylabel("coupler_amp")
    ax.set_xlabel("qubit_amp")
    ax.set_title(q_label)



if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    import matplotlib.pyplot as plt
    ds = load_xarray_h5(r"data/QPU_project/2025-08-26/#959_LCH_CZ_leakage_151528/ds_raw.h5")
    print(ds)
    plt_data = ds.sel(qubit="q0")
    fig, ax = plt.subplots()
    plot_individual_data_with_fit(ax, plt_data, "q0")
    plt.show()