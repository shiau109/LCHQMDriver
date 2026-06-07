"""Analysis wrappers for the LCH_qubit_spectroscopy_flux node.

These thin wrappers delegate the actual fitting to the scqat
``QubitSpectroscopyFluxEstimator``, which collapses the 2-D ``(flux_bias,
detuning)`` map into a 1-D ``qubit_frequency(flux)`` trace by fitting the qubit
peak flux-by-flux (most-prominent single Lorentzian per slice), with strict
window enforcement and robust width/amplitude outlier rejection.

The downstream flux-dependence model fit (the flux-tunable transmon arch) is
deferred — see the node's ``update_state`` (currently a no-op).

scqat is imported lazily (only inside the fit call) so the node still imports
without scqat installed; the official nodes never need it.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import xarray as xr

from qualibrate import QualibrationNode
from qualibration_libs.data import add_amplitude_and_phase, convert_IQ_to_V


def process_raw_dataset(ds: xr.Dataset, node: QualibrationNode) -> xr.Dataset:
    """Convert the raw I/Q to volts and attach the coordinates the estimator and
    plots need: the absolute drive frequency ``full_freq`` (from the xy line) and
    the flux-line ``current`` / ``attenuated_current`` (kept for the deferred
    downstream step)."""
    # Convert the 'I' and 'Q' quadratures from demodulation units to V.
    ds = convert_IQ_to_V(ds, node.namespace["qubits"])
    # Add the amplitude and phase to the raw dataset.
    ds = add_amplitude_and_phase(ds, "detuning", subtract_slope_flag=True)
    # Add the absolute drive frequency as a coordinate (qubit, detuning).
    full_freq = np.array([ds.detuning + q.xy.RF_frequency for q in node.namespace["qubits"]])
    ds = ds.assign_coords(full_freq=(["qubit", "detuning"], full_freq))
    ds.full_freq.attrs = {"long_name": "RF frequency", "units": "Hz"}
    # Add the current axis of the flux line for plotting / later analysis.
    current = ds.flux_bias / node.parameters.input_line_impedance_in_ohm
    ds = ds.assign_coords({"current": (["flux_bias"], current.data)})
    ds.current.attrs = {"long_name": "Current", "units": "A"}
    attenuation_factor = 10 ** (-node.parameters.line_attenuation_in_db / 20)
    attenuated_current = ds.current * attenuation_factor
    ds = ds.assign_coords({"attenuated_current": (["flux_bias"], attenuated_current.values)})
    ds.attenuated_current.attrs = {"long_name": "Attenuated Current", "units": "A"}
    return ds


def fit_raw_data(ds: xr.Dataset, node: QualibrationNode) -> Tuple[Dict, Dict]:
    """Fit the qubit peak flux-by-flux for every qubit with the scqat
    ``QubitSpectroscopyFluxEstimator``.

    Returns
    -------
    (sep_results, fit_results)
        ``sep_results[qubit] = (slice_ds, estimator_results)`` — the per-qubit
        dataset slice and full estimator output (a peak point-cloud), kept so
        ``plot_data`` can redraw the figure without refitting.
        ``fit_results[qubit]`` — a compact scalar summary (peak / kept / outlier
        counts, qubit-frequency span over the kept peaks) used for logging /
        outcomes.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.qubit_spectroscopy_flux import QubitSpectroscopyFluxEstimator

    estimator = QubitSpectroscopyFluxEstimator()
    sep_results: Dict = {}
    fit_results: Dict = {}
    n_sigma = float(getattr(node.parameters, "outlier_n_sigma", 3.0))
    prominence = float(getattr(node.parameters, "peak_prominence", 0.1))
    max_peaks = getattr(node.parameters, "max_peaks_per_flux", None)

    for sq in repetition_data(ds, repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        results = estimator.analyze(
            sq, output_dir=None, skip_figures=True,
            n_sigma=n_sigma, prominence=prominence, max_peaks=max_peaks,
        )[0]
        sep_results[qubit_name] = (sq, results)

        # Qubit-frequency span computed over the kept (good) peaks only.
        peak_freq = np.asarray(results.get("peak_full_freq", results["peak_detuning"]), dtype=float)
        good = np.asarray(results["good"], dtype=bool)
        freq_good = peak_freq[good] if peak_freq.size else peak_freq
        any_good = freq_good.size > 0 and bool(np.isfinite(freq_good).any())
        fit_results[qubit_name] = {
            "success": bool(results["n_good"] > 0),
            "n_peaks": int(results["n_peaks"]),
            "n_in_window": int(results["n_in_window"]),
            "n_good": int(results["n_good"]),
            "n_outlier": int(results["n_outlier"]),
            "n_flux": int(results["n_flux"]),
            "freq_min": float(np.nanmin(freq_good)) if any_good else float("nan"),
            "freq_max": float(np.nanmax(freq_good)) if any_good else float("nan"),
            "has_full_freq": "peak_full_freq" in results,
        }

    return sep_results, fit_results


def log_fitted_results(fit_results: Dict, log_callable=None) -> None:
    """Log a per-qubit summary of the flux-by-flux peak fit."""
    if log_callable is None:
        log_callable = logging.getLogger(__name__).info
    for q, fr in fit_results.items():
        s = (
            f"Results for qubit {q}: "
            f"kept {fr['n_good']}/{fr['n_peaks']} peaks across {fr['n_flux']} flux points "
            f"({fr['n_in_window']} in-window, {fr['n_outlier']} outliers) | "
            f"qubit frequency {1e-9 * fr['freq_min']:.3f} to {1e-9 * fr['freq_max']:.3f} GHz | "
            f"{'SUCCESS!' if fr['success'] else 'FAIL!'}"
        )
        log_callable(s)
