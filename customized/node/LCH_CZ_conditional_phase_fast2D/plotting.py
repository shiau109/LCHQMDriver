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

    # Select data for the specific qubit
    phase_on = np.arctan2( qubit_data.sel(ctrl_switch=True).sel(basis=1), qubit_data.sel(ctrl_switch=True).sel(basis=0))
    phase_off = np.arctan2( qubit_data.sel(ctrl_switch=False).sel(basis=1), qubit_data.sel(ctrl_switch=False).sel(basis=0))
    # Plot 2D map based on available data
    # Plot phase_diff as 2D heatmap
    phase_diff = phase_on - phase_off
    phase_diff = np.degrees(phase_diff)
    print(phase_diff)

    # Plot phase_diff as 2D heatmap
    phase_diff.state.plot(
        ax=ax,
        x="qubit_amp",
        y="coupler_amp",
        add_colorbar=True,
        cmap="RdBu_r"
    )

    
    ax.set_ylabel("coupler_amp")
    ax.set_xlabel("qubit_amp")
    ax.set_title(q_label)


def plot_phase_on_off_maps(qubit_data: xr.Dataset | xr.DataArray, q_label: str | None = None, figsize=(12, 5)):
    """Create a figure with two subplots: phase_on and phase_off as 2D heatmaps.

    Parameters
    ----------
    qubit_data : xr.Dataset or xr.DataArray
        Dataset (e.g. ds[["state"]].sel(qubit="q1")) or DataArray containing the
        measurement with coordinates `ctrl_switch` and `basis` and dims `qubit_amp`, `coupler_amp`.
    q_label : str | None
        Optional label to show in the subplot titles.
    figsize : tuple
        Matplotlib figure size.

    Returns
    -------
    matplotlib.figure.Figure, numpy.ndarray
        The created figure and axes array (2 subplots).
    """
    # Normalize input to a DataArray
    if isinstance(qubit_data, xr.Dataset):
        if "state" in qubit_data.data_vars:
            data = qubit_data["state"]
        else:
            # pick first data variable if name differs
            data = next(iter(qubit_data.data_vars.values()))
    else:
        data = qubit_data

    # Ensure required coordinates/dims exist
    if not ("ctrl_switch" in data.coords and "basis" in data.dims):
        raise RuntimeError("Input data must contain 'ctrl_switch' coordinate and 'basis' dimension")

    # Compute phase (arctan2) for ctrl ON and OFF
    phase_on = np.arctan2(data.sel(ctrl_switch=True).sel(basis=1), data.sel(ctrl_switch=True).sel(basis=0))
    phase_off = np.arctan2(data.sel(ctrl_switch=False).sel(basis=1), data.sel(ctrl_switch=False).sel(basis=0))

    # Convert to degrees for easier interpretation
    phase_on_deg = np.degrees(phase_on)
    phase_off_deg = np.degrees(phase_off)

    # Create figure with two subplots
    fig, axes = plt.subplots(1, 2, figsize=figsize, constrained_layout=True)

    # Plot phase_on
    phase_on_deg.plot(
        ax=axes[0],
        x="qubit_amp",
        y="coupler_amp",
        add_colorbar=True,
        cmap="viridis",
    )
    axes[0].set_title(f"{q_label} phase_on" if q_label else "phase_on")
    axes[0].set_xlabel("qubit_amp")
    axes[0].set_ylabel("coupler_amp")

    # Plot phase_off
    phase_off_deg.plot(
        ax=axes[1],
        x="qubit_amp",
        y="coupler_amp",
        add_colorbar=True,
        cmap="viridis",
    )
    axes[1].set_title(f"{q_label} phase_off" if q_label else "phase_off")
    axes[1].set_xlabel("qubit_amp")
    axes[1].set_ylabel("coupler_amp")

    return fig, axes



if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    ds = load_xarray_h5(r"data/QPU_project/2025-08-25/#924_LCH_CZ_conditional_phase_221842/ds_raw.h5")
    print(ds["state"])
    plt_data = ds[["state"]].sel(qubit="q1")
    fig, ax = plt.subplots()
    plot_individual_data_with_fit(ax, plt_data, "q1")
    plot_phase_on_off_maps(plt_data, "q1")
    plt.show()