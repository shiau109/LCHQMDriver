
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

    plt_data = ds.sel(qubit="q1")
    ds_fit = fit_cos_basis(plt_data)
    # plot_rawdata_at_index(plt_data,-0.06,-0.10, ds_fit)
    # plot_fit_results_heatmap(ds_fit)
    fig = plot_fit_results_diff_heatmap(ds_fit)

    return fig


def fit_cos_basis(da: xr.DataArray):
    """
    Fit A*cos(2*pi*x+phi)+c to data along 'basis' axis for each (qubit_amp, coupler_amp, ctrl_switch).
    Returns Dataset with dims (qubit_amp, coupler_amp, ctrl_switch), variables 'A' and 'phi'.
    """
    import numpy as np
    from scipy.optimize import curve_fit

    # Ensure basis axis exists
    if "basis" not in da.dims:
        raise ValueError("Input DataArray must have 'basis' axis")

    xvals = da.coords["basis"].values
    # If basis is not float, convert to float
    xvals = np.asarray(xvals, dtype=float)

    # Prepare output arrays
    shape = [da.sizes.get(dim) for dim in da.dims if dim != "basis"]
    dims = [dim for dim in da.dims if dim != "basis"]
    coords = {dim: da.coords[dim] for dim in dims}

    # We'll iterate over all indices except basis
    idxs = np.indices(shape).reshape(len(shape), -1).T
    A_arr = np.full(shape, np.nan)
    phi_arr = np.full(shape, np.nan)
    c_arr = np.full(shape, np.nan)

    def cos_func(x, A, phi, c):
        return A * np.cos(2 * np.pi * x + phi) + c

    for idx in idxs:
        # Build dict for slicing
        sel = {dim: coords[dim][i] for dim, i in zip(dims, idx)}
        y = da.sel(**sel)["state"].values
        # Initial guess: A=0.5, phi=0, c=0.5
        p0 = [0.5, 0.0, 0.5]
        try:
            bounds = ([0, -np.pi, -np.inf], [np.inf, np.pi, np.inf])
            popt, _ = curve_fit(cos_func, xvals, y, p0=p0, bounds=bounds)
            A_arr[tuple(idx)] = popt[0]
            phi_arr[tuple(idx)] = popt[1]
            c_arr[tuple(idx)] = popt[2]
        except Exception:
            continue

    # Build output Dataset
    ds_out = xr.Dataset({
        "A": (dims, A_arr),
        "phi": (dims, phi_arr),
        "c": (dims, c_arr)
    }, coords=coords)
    return ds_out

# Print raw data along basis for a given index

def plot_rawdata_at_index(da: xr.Dataset, qubit_amp=None, coupler_amp=None, ds_fit=None):
    """
    Print and plot raw data along basis for given (qubit_amp, coupler_amp) index.
    If ds_fit is provided, also plot the fitted curve for both ctrl_switch values.
    """
    sel = {}
    if qubit_amp is not None:
        sel["qubit_amp"] = qubit_amp
    if coupler_amp is not None:
        sel["coupler_amp"] = coupler_amp

    arr = da.sel(coupler_amp=coupler_amp, qubit_amp=qubit_amp, method='nearest')
    print(arr)

    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    basis = arr.coords["basis"].values
    y_true = arr["state"].sel(ctrl_switch=True).values
    y_false = arr["state"].sel(ctrl_switch=False).values
    ax.plot(basis, y_true, marker="o", label="raw True")
    ax.plot(basis, y_false, marker="x", label="raw False")

    # If ds_fit is provided, plot fit lines
    if ds_fit is not None:
        fit_true = ds_fit.sel(coupler_amp=coupler_amp, qubit_amp=qubit_amp, method='nearest').sel(ctrl_switch=True)
        fit_false = ds_fit.sel(coupler_amp=coupler_amp, qubit_amp=qubit_amp, method='nearest').sel(ctrl_switch=False)
        def fit_curve(x, A, phi, c):
            import numpy as np
            return A * np.cos(2 * np.pi * x + phi) + c
        y_fit_true = fit_curve(basis, fit_true["A"].values, fit_true["phi"].values, fit_true["c"].values)
        y_fit_false = fit_curve(basis, fit_false["A"].values, fit_false["phi"].values, fit_false["c"].values)
        ax.plot(basis, y_fit_true, color="C0", linestyle="--", label="fit True")
        ax.plot(basis, y_fit_false, color="C1", linestyle="--", label="fit False")

    ax.set_xlabel("basis")
    ax.set_ylabel("raw value / fit")
    ax.set_title(f"Raw data at {sel}")
    ax.grid(True)
    ax.legend()
    # plt.show() removed; fig is returned
    return fig

# Plot A, phi, c as 2D heatmaps for each ctrl_switch value
def plot_fit_results_heatmap(ds_fit: xr.Dataset):
    """
    Plot A, phi, c as 2D heatmaps (qubit_amp × coupler_amp) for each ctrl_switch value in ds_fit.
    """
    import matplotlib.pyplot as plt
    figs = []
    for ctrl_val in ds_fit.coords["ctrl_switch"].values:
        fig, axes = plt.subplots(1, 3, figsize=(15, 5))
        for i, var in enumerate(["A", "phi", "c"]):
            arr = ds_fit[var].sel(ctrl_switch=ctrl_val)
            im = arr.plot(ax=axes[i], x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="viridis")
            axes[i].set_title(f"{var} (ctrl_switch={ctrl_val})")
        fig.suptitle(f"Fit results for ctrl_switch={ctrl_val}")
        plt.tight_layout()
    # plt.show() removed; fig is returned
        figs.append(fig)
    return figs if len(figs) > 1 else figs[0]

# Plot difference/ratio heatmaps between ctrl_switch True/False
def plot_fit_results_diff_heatmap(ds_fit: xr.Dataset):
    """
    Show 3 heatmaps:
    1. A(ctrl_switch=True) / A(ctrl_switch=False)
    2. phi(ctrl_switch=True) - phi(ctrl_switch=False)
    3. c(ctrl_switch=True) - c(ctrl_switch=False)
    """
    import matplotlib.pyplot as plt
    # Select True/False
    A_true = ds_fit["A"].sel(ctrl_switch=True)
    A_false = ds_fit["A"].sel(ctrl_switch=False)
    phi_true = ds_fit["phi"].sel(ctrl_switch=True)
    phi_false = ds_fit["phi"].sel(ctrl_switch=False)
    c_true = ds_fit["c"].sel(ctrl_switch=True)
    c_false = ds_fit["c"].sel(ctrl_switch=False)

    # Compute maps
    A_ratio = A_true / A_false
    import numpy as np
    phi_diff = phi_true - phi_false
    # Wrap phi_diff to [-pi, pi]
    phi_diff = xr.apply_ufunc(
        lambda x: np.where(x > np.pi, x - 2 * np.pi, np.where(x < -np.pi, x + 2 * np.pi, x)),
        phi_diff
    )
    c_diff = c_true - c_false

    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    im1 = A_ratio.plot(ax=axes[0], x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="viridis")
    axes[0].set_title("A ratio (True/False)")
    axes[0].set_xlabel("qubit_amp")
    axes[0].set_ylabel("coupler_amp")
    im2 = phi_diff.plot(ax=axes[1], x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="RdBu_r")
    axes[1].set_title("phi diff (True-False)")
    axes[1].set_xlabel("qubit_amp")
    axes[1].set_ylabel("coupler_amp")
    im3 = c_diff.plot(ax=axes[2], x="qubit_amp", y="coupler_amp", add_colorbar=True, cmap="RdBu_r")
    axes[2].set_title("c diff (True-False)")
    axes[2].set_xlabel("qubit_amp")
    axes[2].set_ylabel("coupler_amp")
    fig.suptitle("Fit result differences: ctrl_switch True vs False")
    plt.tight_layout()
    # plt.show() removed; fig is returned
    return fig


# Example usage in __main__
if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    import matplotlib.pyplot as plt
    ds = load_xarray_h5(r"data/QPU_project/2025-08-27/#1032_LCH_CZ_slow2D_111203/ds_raw.h5")
    print(ds)
    plt_data = ds.sel(qubit="q1")
    ds_fit = fit_cos_basis(plt_data)
    # plot_rawdata_at_index(plt_data,-0.06,-0.10, ds_fit)
    plot_fit_results_heatmap(ds_fit)
    plot_fit_results_diff_heatmap(ds_fit)
    plt.show()