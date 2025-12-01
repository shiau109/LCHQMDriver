
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
        ds_fit = fit_on_off_cos(plot_ds)
        plot_individual_data_with_fit(ax, plot_ds, q_label, ds_fit)

    grid.fig.suptitle("CZ conditional phase")
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

    # If fit is provided, plot fitted curves for ON/OFF and show A, phi
    if fit is not None and "fit" in fit:
        fit_on = fit["fit"].sel(ctrl_switch=True).values
        fit_off = fit["fit"].sel(ctrl_switch=False).values
        ax.plot(x, fit_on, color="C0", linestyle="--", label=(q_label or "") + " fit_on")
        ax.plot(x, fit_off, color="C1", linestyle="--", label=(q_label or "") + " fit_off")
        # Show A and phi as text
        A_on = fit["A"].sel(ctrl_switch=True).item()
        phi_on = fit["phi"].sel(ctrl_switch=True).item()
        A_off = fit["A"].sel(ctrl_switch=False).item()
        phi_off = fit["phi"].sel(ctrl_switch=False).item()
        txt = f"ON: A={A_on:.3f}, phi={phi_on:.3f}\nOFF: A={A_off:.3f}, phi={phi_off:.3f}\n Diff: A={(A_on/A_off):.3f}, phi={(phi_on-phi_off):.3f}"
        ax.text(0.05, 0.95, txt, transform=ax.transAxes, fontsize=10, va='top', ha='left', bbox=dict(facecolor='white', alpha=0.7, edgecolor='none'))

    ax.set_xlabel("basis")
    ax.set_ylabel("phase (deg)")
    ax.legend()
    ax.grid(True)


def fit_on_off_cos(qubit_data: xr.Dataset):
    """
    Fit both on (ctrl_switch=True) and off (ctrl_switch=False) to A*cos(2*pi*x+phi)+c.
    Returns a dataset with dims (ctrl_switch, basis) and variables 'fit', 'A', 'phi', 'c'.
    Compatible with plot_individual_data_with_fit for showing the fitting curve.
    """
    import numpy as np
    from scipy.optimize import curve_fit
    # Normalize input to DataArray
    if isinstance(qubit_data, xr.Dataset):
        if "state" in qubit_data.data_vars:
            data = qubit_data["state"]
        else:
            data = list(qubit_data.data_vars.values())[0]
    else:
        data = qubit_data

    x = np.asarray(data["basis"].values, dtype=float)
    out = {}
    for ctrl_val in [True, False]:
        y = data.sel(ctrl_switch=ctrl_val).values
        p0 = [0.5, 0.0, 0.5]
        bounds = ([0, -np.pi, -np.inf], [np.inf, np.pi, np.inf])
        try:
            popt, _ = curve_fit(lambda x, A, phi, c: A * np.cos(2 * np.pi * x + phi) + c, x, y, p0=p0, bounds=bounds)
            fit_curve = popt[0] * np.cos(2 * np.pi * x + popt[1]) + popt[2]
            out[ctrl_val] = {
                "fit": fit_curve,
                "A": popt[0],
                "phi": popt[1],
                "c": popt[2]
            }
        except Exception:
            out[ctrl_val] = {
                "fit": np.full_like(x, np.nan),
                "A": np.nan,
                "phi": np.nan,
                "c": np.nan
            }

    # Build output Dataset
    ds_fit = xr.Dataset({
        "fit": (("ctrl_switch", "basis"), np.stack([out[True]["fit"], out[False]["fit"]])),
        "A": ("ctrl_switch", [out[True]["A"], out[False]["A"]]),
        "phi": ("ctrl_switch", [out[True]["phi"], out[False]["phi"]]),
        "c": ("ctrl_switch", [out[True]["c"], out[False]["c"]])
    }, coords={"ctrl_switch": [True, False], "basis": x})
    return ds_fit

if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    ds = load_xarray_h5(r"data/QPU_project/2025-08-28/#1150_LCH_CZ_conditional_phase_110315/ds_raw.h5")
    print(ds["state"])
    plt_data = ds[["state"]].sel(qubit="q1")
    fig, ax = plt.subplots()
    ds_fit = fit_on_off_cos(plt_data)
    print(ds_fit)
    plot_individual_data_with_fit(ax, plt_data, "q1", ds_fit)
    plt.show()