"""Plotting for the LCH_resonator_spectroscopy_flux node.

A single combined figure per qubit overlaying, on one absolute-frequency axis:
  * the 2-D ``|IQ|`` amplitude map (raw data) over (flux, frequency),
  * the per-flux fitted resonator centre (kept points; rejected ones as red x),
  * the dispersive centre-frequency(flux) fit curve and the sweet-spot marker.

Everything is drawn from the already-computed analyzer results (no refitting), so
the scqat analyzers are not involved here.
"""

from typing import Dict, Optional

import numpy as np
import matplotlib.pyplot as plt


def plot_combined(
    sep_results: Dict,
    dispersion_sep: Dict,
    flux_offsets: Optional[Dict] = None,
    flux_offset_label: str = "flux offset",
    readout_freqs: Optional[Dict] = None,
    readout_freq_label: str = "readout freq",
) -> Dict:
    """Build one combined figure per qubit.

    Parameters
    ----------
    sep_results : dict
        ``{qubit: (slice_ds, vs_flux_results)}`` from ``fit_raw_data`` — carries
        the 2-D amplitude map, the per-flux centres and the good/outlier masks.
    dispersion_sep : dict
        ``{qubit: (trace_ds, dispersion_results)}`` from ``fit_flux_dependence`` —
        carries the dispersive fit curve and the sweet spot.
    flux_offsets : dict, optional
        ``{qubit_name: offset_in_volts}`` — when given, a vertical line is drawn at
        ``offset_in_volts`` on that qubit's map (the flux source's operating point).
        Entries that are ``None`` / non-finite are skipped.
    flux_offset_label : str
        Legend label for the vertical offset line.
    readout_freqs : dict, optional
        ``{qubit_name: readout_freq_in_hz}`` — when given, a horizontal line is drawn
        at the qubit's current resonator readout frequency. Entries that are ``None`` /
        non-finite are skipped.
    readout_freq_label : str
        Legend label for the horizontal readout-frequency line.

    Returns
    -------
    dict
        ``{qubit_name: matplotlib.figure.Figure}`` — one figure per qubit.
    """
    figures: Dict = {}
    for qubit_name, (_slice_ds, vs) in sep_results.items():
        flux = np.asarray(vs["flux_bias"], dtype=float)
        amplitude_map = np.asarray(vs["amplitude_map"], dtype=float)  # (flux, detuning)
        good = np.asarray(vs["good"], dtype=bool)
        outlier = np.asarray(vs["outlier"], dtype=bool)

        # Absolute RF frequency axis when available, else detuning.
        has_full = "full_freq" in vs and "center_full_freq" in vs
        if has_full:
            yvals = np.asarray(vs["full_freq"], dtype=float) / 1e9
            centers = np.asarray(vs["center_full_freq"], dtype=float) / 1e9
            scale, ylabel = 1e9, "RF frequency (GHz)"
        else:
            yvals = np.asarray(vs["detuning"], dtype=float) / 1e6
            centers = np.asarray(vs["center_detuning"], dtype=float) / 1e6
            scale, ylabel = 1e6, "Detuning (MHz)"

        fig, ax = plt.subplots(figsize=(10, 6), dpi=120)

        # (1) Raw 2-D |IQ| amplitude map.
        pcm = ax.pcolormesh(flux, yvals, amplitude_map.T, shading="auto", cmap="viridis")
        fig.colorbar(pcm, ax=ax, label="Amplitude |IQ| (arb. u.)")

        # (2) Per-flux fitted resonator centres (kept) and rejected outliers.
        ax.plot(flux[good], centers[good], "o", color="white", ms=4, mec="black", mew=0.4,
                label="centre (kept)")
        if outlier.any():
            ax.plot(flux[outlier], centers[outlier], "x", color="red", ms=7, mew=1.5,
                    label="rejected")

        # (3) Dispersive fit curve + sweet spot.
        disp_entry = dispersion_sep.get(qubit_name)
        if disp_entry is not None:
            _, disp = disp_entry
            fit_flux = np.asarray(disp.get("fit_flux", []), dtype=float)
            fit_freq = np.asarray(disp.get("fit_freq", []), dtype=float)
            if fit_freq.size and np.isfinite(fit_freq).any():
                # White halo under an orange line so it reads over the colormap.
                ax.plot(fit_flux, fit_freq / scale, "-", color="white", lw=3.0)
                ax.plot(fit_flux, fit_freq / scale, "-", color="C1", lw=1.5,
                        label="dispersive fit")
            ss_flux = float(disp.get("sweet_spot_flux", np.nan))
            ss_freq = float(disp.get("sweet_spot_freq", np.nan))
            if np.isfinite(ss_flux) and np.isfinite(ss_freq):
                ax.plot([ss_flux], [ss_freq / scale], "*", color="yellow", ms=15,
                        mec="black", mew=0.6, label="sweet spot")

        # (4) Vertical line at the flux source's operating (idle) offset.
        if flux_offsets is not None:
            off = flux_offsets.get(qubit_name)
            if off is not None and np.isfinite(off):
                ax.axvline(float(off), color="magenta", ls="--", lw=1.5, label=flux_offset_label)

        # (5) Horizontal line at the resonator's current readout frequency. On the
        # absolute-frequency axis it sits at the readout frequency; on the detuning
        # axis the detuning is centred on that frequency, so it sits at 0.
        if readout_freqs is not None:
            rf = readout_freqs.get(qubit_name)
            if rf is not None and np.isfinite(rf):
                y_rf = float(rf) / scale if has_full else 0.0
                ax.axhline(y_rf, color="cyan", ls=":", lw=1.5, label=readout_freq_label)

        ax.set_xlim(float(flux.min()), float(flux.max()))
        ax.set_ylim(float(yvals.min()), float(yvals.max()))
        ax.set_xlabel("Flux bias (V)")
        ax.set_ylabel(ylabel)
        n_good = int(good.sum())
        ax.set_title(f"{qubit_name}: resonator spectroscopy vs flux (kept {n_good}/{flux.size})")
        ax.legend(fontsize=8, loc="best")
        fig.tight_layout()
        figures[qubit_name] = fig
    return figures
