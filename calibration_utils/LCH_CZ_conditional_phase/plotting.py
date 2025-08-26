from typing import List
import xarray as xr
from matplotlib.axes import Axes

from qualang_tools.units import unit
from qualibration_libs.plotting import QubitGrid, grid_iter
from qualibration_libs.analysis import decay_exp
from quam_builder.architecture.superconducting.qubit import AnyTransmon

import numpy as np
u = unit(coerce_to_integer=True)

import matplotlib.pyplot as plt


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


def plot_individual_data_with_fit(ax: Axes, qubit_data: xr.Dataset, q_label:str=None, fit: xr.Dataset = None):
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


    # If the user passed an xr.Dataset, prefer plotting 'state' as 2D heatmap.
    if isinstance(qubit_data, xr.Dataset):
        ds = qubit_data
        if "state" in ds.data_vars:
            var = ds["state"]
            # choose ctrl_switch=True slice if available
            if "ctrl_switch" in var.coords:
                try:
                    var_plot = var.sel(ctrl_switch=True)
                except Exception:
                    var_plot = var.mean(dim="ctrl_switch")
            else:
                var_plot = var
            # plot 2D heatmap if dims exist
            if "qubit_amp" in var_plot.dims and "coupler_amp" in var_plot.dims:
                var_plot.plot(ax=ax, x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="viridis")
                ax.set_title(q_label or "")
                return
        # fallback to 'I' quadrature if present
        if "I" in ds.data_vars:
            var = ds["I"]
            if "ctrl_switch" in var.coords:
                try:
                    var_plot = var.sel(ctrl_switch=True)
                except Exception:
                    var_plot = var.mean(dim="ctrl_switch")
            else:
                var_plot = var
            if "qubit_amp" in var_plot.dims and "coupler_amp" in var_plot.dims:
                var_plot.plot(ax=ax, x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="RdBu_r")
                ax.set_title(q_label or "")
                return

    # Normalize input to a DataArray for basis plotting
    if isinstance(qubit_data, xr.Dataset):
        # prefer a variable called 'state' if present
        if "state" in qubit_data.data_vars:
            data = qubit_data["state"]
        else:
            # pick the first data variable
            data = list(qubit_data.data_vars.values())[0]
    else:
        data = qubit_data

    # Ensure required coordinates/dims exist for basis plotting
    if not ("ctrl_switch" in data.coords and "basis" in data.dims):
        raise RuntimeError("Input data must contain 'ctrl_switch' coordinate and 'basis' dimension")

    # Select ON / OFF slices
    on = data.sel(ctrl_switch=True)
    off = data.sel(ctrl_switch=False)



    # x-axis: basis coordinate values (may be ints 0/1 or labels)
    x = data["basis"].values

    # Compute phase values (degrees) per-basis if possible


    # Plot phase_on and phase_off vs basis
    ax.plot(x, on, marker="o", label=(q_label or "") + " phase_on")
    ax.plot(x, off, marker="x", label=(q_label or "") + " phase_off")
    ax.set_xlabel("basis")
    ax.set_ylabel("phase (deg)")
    ax.legend()
    ax.grid(True)

if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    ds = load_xarray_h5(r"data/QPU_project/2025-08-26/#941_LCH_CZ_conditional_phase_120536/ds_raw.h5")
    print(ds["state"])
    plt_data = ds[["state"]].sel(qubit="q1")
    fig, ax = plt.subplots()
    plot_individual_data_with_fit(ax, plt_data, "q1")
    plt.show()