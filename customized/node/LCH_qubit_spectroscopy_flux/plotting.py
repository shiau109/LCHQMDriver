"""Plotting for the LCH_qubit_spectroscopy_flux node.

A single combined figure per qubit overlaying, on one absolute-frequency axis:
  * the 2-D signal map (raw data) over (flux, frequency),
  * the per-flux fitted qubit centre (kept points; rejected ones as red x).

The flux-dependence model fit curve (transmon arch) is deferred, so it is not
drawn yet. Everything is taken from the already-computed analyzer results.
"""

from typing import Dict

import numpy as np
import matplotlib.pyplot as plt


def plot_combined(sep_results: Dict) -> Dict:
    """Build one combined figure per qubit.

    Parameters
    ----------
    sep_results : dict
        ``{qubit: (slice_ds, vs_flux_results)}`` from ``fit_raw_data`` — carries
        the 2-D signal map, the per-flux centres and the good/outlier masks.

    Returns
    -------
    dict
        ``{qubit_name: matplotlib.figure.Figure}`` — one figure per qubit.
    """
    figures: Dict = {}
    for qubit_name, (_slice_ds, vs) in sep_results.items():
        flux = np.asarray(vs["flux_bias"], dtype=float)
        amplitude_map = np.asarray(vs["amplitude_map"], dtype=float)  # (flux, detuning)
        peak_flux = np.asarray(vs["peak_flux"], dtype=float)
        good = np.asarray(vs["good"], dtype=bool)
        outlier = np.asarray(vs["outlier"], dtype=bool)

        # Absolute RF frequency axis when available, else detuning.
        has_full = "full_freq" in vs and "peak_full_freq" in vs
        if has_full:
            yvals = np.asarray(vs["full_freq"], dtype=float) / 1e9
            peak_y = np.asarray(vs["peak_full_freq"], dtype=float) / 1e9
            ylabel = "Qubit RF frequency (GHz)"
        else:
            yvals = np.asarray(vs["detuning"], dtype=float) / 1e6
            peak_y = np.asarray(vs["peak_detuning"], dtype=float) / 1e6
            ylabel = "Detuning (MHz)"

        fig, ax = plt.subplots(figsize=(10, 6), dpi=120)

        # (1) Raw 2-D signal map.
        pcm = ax.pcolormesh(flux, yvals, amplitude_map.T, shading="auto", cmap="viridis")
        fig.colorbar(pcm, ax=ax, label="Signal (arb. u.)")

        # (2) All fitted qubit peaks (kept) and rejected outliers, as a point-cloud.
        if good.any():
            ax.plot(peak_flux[good], peak_y[good], "o", color="white", ms=4, mec="black", mew=0.4,
                    label="peaks (kept)")
        if outlier.any():
            ax.plot(peak_flux[outlier], peak_y[outlier], "x", color="red", ms=7, mew=1.5,
                    label="rejected")

        ax.set_xlim(float(flux.min()), float(flux.max()))
        ax.set_ylim(float(yvals.min()), float(yvals.max()))
        ax.set_xlabel("Flux bias (V)")
        ax.set_ylabel(ylabel)
        n_good = int(good.sum())
        n_peaks = int(good.size)
        ax.set_title(f"{qubit_name}: qubit spectroscopy vs flux (kept {n_good}/{n_peaks} peaks)")
        ax.legend(fontsize=8, loc="best")
        fig.tight_layout()
        figures[qubit_name] = fig
    return figures
