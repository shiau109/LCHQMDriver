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
        plot_individual_data_with_fit(ax, ds, qubit)

    grid.fig.suptitle("ZZ interation with Coupler Offset")
    grid.fig.set_size_inches(15, 9)
    grid.fig.tight_layout()
    return grid.fig


def plot_individual_data_with_fit(ax: Axes, ds: xr.Dataset, qubit: dict[str, str], fit: xr.Dataset = None):
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
    qubit_data = ds.sel(qubit=qubit["qubit"])
    
    # Plot 2D map based on available data
    if hasattr(qubit_data, "state"):
        # Plot state as 2D heatmap
        qubit_data.state.plot(
            ax=ax,
            x="idle_time",
            y="coupler_z",
            add_colorbar=True,
            cmap="viridis"
        )
        
    elif hasattr(qubit_data, "I"):
        # Plot I quadrature as 2D heatmap (convert to mV)
        (qubit_data.I * 1e3).plot(
            ax=ax,
            x="idle_time", 
            y="coupler_z",
            add_colorbar=True,
            cmap="RdBu_r"
        )
        
    elif hasattr(qubit_data, "IQ_abs"):
        # Plot IQ amplitude as 2D heatmap
        qubit_data.IQ_abs.plot(
            ax=ax,
            x="idle_time",
            y="coupler_z", 
            add_colorbar=True,
            cmap="plasma"
        )
        
    else:
        raise RuntimeError("The dataset must contain either 'state', 'I', or 'IQ_abs' for the plotting function to work.")
    
    ax.set_ylabel("coupler offset (V)")
    ax.set_xlabel("Idle time (ns)")
    ax.set_title(qubit["qubit"])

