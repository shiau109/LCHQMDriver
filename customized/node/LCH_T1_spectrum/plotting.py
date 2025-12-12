
from typing import List
import xarray as xr
from matplotlib.axes import Axes
from qualibration_libs.analysis import decay_exp
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from qualibration_libs.plotting import QubitGrid, grid_iter


def plot_raw_data_with_fit(ds: xr.Dataset, qubits: List[AnyTransmon], fits: xr.Dataset=None):
    """
    Plots T1 data with fit results for multiple qubits.

    Parameters:
    -----------
    ds : xr.Dataset
        Dataset containing the raw data.
    qubits : List[AnyTransmon]
        List of qubits involved in the sequence.
    node_parameters : Parameters
        Parameters related to the node.
    fits : xr.Dataset
        Dataset containing the fit results for the T1 data.

    Returns:
    --------
    matplotlib.figure.Figure
        The figure containing the plots.
    """
    grid = QubitGrid(ds, [q.grid_location for q in qubits])

    for ax, qubit in grid_iter(grid):
        q_label = qubit["qubit"]  
        plot_ds = ds.sel(qubit=qubit["qubit"])

        
        plot_individual_data_with_fit(ax, plot_ds, q_label)

    grid.fig.suptitle("T1 vs. idle time")
    grid.fig.set_size_inches(15, 9)
    grid.fig.tight_layout()
    return grid.fig


def plot_individual_data_with_fit(ax: Axes, ds: xr.Dataset, q_label: str, fit: xr.Dataset = None):
    """Plot individual qubit data on a given axis."""
    if fit:
        fitted = decay_exp(
            ds.idle_time,
            fit.fit_data.sel(fit_vals="a"),
            fit.fit_data.sel(fit_vals="offset"),
            fit.fit_data.sel(fit_vals="decay"),
        )
    else:
        fitted = None

    # If flux_amp axis exists, plot 2D heatmap
    if hasattr(ds, "signal") and "flux_amp" in ds.signal.dims:
        ds.signal.plot(ax=ax, x="idle_time", y="flux_amp", add_colorbar=True, cmap="viridis")
        ax.set_ylabel("flux_amp")
        ax.set_xlabel("Idle time [ns]")
        ax.set_title(q_label + " (2D heatmap)")
    elif hasattr(ds, "signal"):
        ds.signal.plot(ax=ax)
        if fitted is not None:
            ax.plot(ds.idle_time, fitted, "r--")
        ax.set_ylabel("Signal")
        ax.set_xlabel("Idle time [ns]")
        ax.set_title(q_label)
    else:
        raise RuntimeError("The dataset must contain 'signal' for the plotting function to work.")

    if fit is not None:
        _add_fit_text(ax, fit)


def _add_fit_text(ax, fit):
    """Add fit results text to the axis."""
    ax.text(
        0.1,
        0.9,
        f"T1 = {1e-3 * fit.tau.values:.1f} ± {1e-3 * fit.tau_error.values:.1f} µs\nSuccess: {fit.success.values}",
        transform=ax.transAxes,
        fontsize=10,
        verticalalignment="top",
        bbox=dict(facecolor="white", alpha=0.5),
    )



# Fit exp decay for each flux_amp
def fit_exp_decay_vs_flux_amp(plt_data):
    """
    Fit exp decay to state vs idle_time for each flux_amp.
    Returns a dataset with tau, offset, amplitude as function of flux_amp.
    """
    import numpy as np
    from scipy.optimize import curve_fit
    idle_time = plt_data.idle_time.values
    flux_amps = plt_data.coords["flux_amp"].values
    tau_arr = np.full_like(flux_amps, np.nan, dtype=float)
    offset_arr = np.full_like(flux_amps, np.nan, dtype=float)
    amp_arr = np.full_like(flux_amps, np.nan, dtype=float)
    def exp_func(t, a, offset, tau):
        return a * np.exp(-t / tau) + offset
    for i, fa in enumerate(flux_amps):
        y = plt_data.sel(flux_amp=fa).state.values
        # Initial guess: a=1, offset=0, tau=idle_time.max()/2
        p0 = [y.max()-y.min(), y.min(), idle_time.max()/2]
        try:
            popt, _ = curve_fit(exp_func, idle_time, y, p0=p0, bounds=([-np.inf, -np.inf, 0], [np.inf, np.inf, np.inf]))
            amp_arr[i] = popt[0]
            offset_arr[i] = popt[1]
            tau_arr[i] = popt[2]
        except Exception:
            continue
    fit_ds = xr.Dataset({
        "tau": ("flux_amp", tau_arr),
        "offset": ("flux_amp", offset_arr),
        "amplitude": ("flux_amp", amp_arr)
    }, coords={"flux_amp": flux_amps})
    return fit_ds

# Plot tau vs flux_amp
def plot_fit_vs_flux_amp(fit_ds):
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots()
    ax.plot(fit_ds["flux_amp"].values, fit_ds["tau"].values, marker="o")
    ax.set_xlabel("flux_amp")
    ax.set_ylabel("Fitted tau (ns)")
    ax.set_title("T1 vs flux_amp")
    ax.grid(True)
    return fig

if __name__ == "__main__":
    from customized.read_data import load_xarray_h5
    import matplotlib.pyplot as plt
    ds = load_xarray_h5(r"data/QPU_project/2025-08-29/#1264_LCH_T1_spectrum_151533/ds_raw.h5")
    print(ds["state"])
    plt_data = ds[["state"]].sel(qubit="q1")
    fig, ax = plt.subplots()
    plot_individual_data_with_fit(ax, plt_data, "q1")
    fit_ds = fit_exp_decay_vs_flux_amp(plt_data)
    plot_fit_vs_flux_amp(fit_ds)
    plt.show()