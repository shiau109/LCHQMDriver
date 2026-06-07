"""Analysis wrappers for the LCH_resonator_spectroscopy_vs_oneflux node.

These thin wrappers delegate the actual fitting to the scqat
``ResonatorSpectroscopyVsFluxAnalyzer``, which collapses the 2-D
``(flux_bias, detuning)`` map into a 1-D ``center_frequency(flux)`` trace by
fitting the resonator dip flux-by-flux (single inverted Lorentzian per slice).

What to do with that trace (sweet-spot / idle-offset / phi0 extraction) is
deliberately deferred — see the node's ``update_state`` (currently a no-op).

scqat is imported lazily (only inside the fit/plot calls) so the node still
imports without scqat installed; the official nodes never need it.
"""

import logging
from typing import Dict, Tuple

import numpy as np
import xarray as xr

from qualibrate import QualibrationNode
from qualibration_libs.data import add_amplitude_and_phase, convert_IQ_to_V


def process_raw_dataset(ds: xr.Dataset, node: QualibrationNode) -> xr.Dataset:
    """Convert the raw I/Q to volts and attach the coordinates the analyzer and
    plots need: the absolute readout frequency ``full_freq`` and the flux-line
    ``current`` / ``attenuated_current`` (kept for the deferred downstream step)."""
    # Convert the 'I' and 'Q' quadratures from demodulation units to V.
    ds = convert_IQ_to_V(ds, node.namespace["qubits"])
    # Add the amplitude and phase to the raw dataset (handy for inspection).
    ds = add_amplitude_and_phase(ds, "detuning", subtract_slope_flag=True)
    # Add the absolute RF frequency as a coordinate (qubit, detuning).
    full_freq = np.array([ds.detuning + q.resonator.RF_frequency for q in node.namespace["qubits"]])
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
    """Fit the resonator dip flux-by-flux for every qubit with the scqat
    ``ResonatorSpectroscopyVsFluxAnalyzer``.

    Returns
    -------
    (sep_results, fit_results)
        ``sep_results[qubit] = (slice_ds, analyzer_results)`` — the per-qubit
        dataset slice and full analyzer output, kept so ``plot_data`` can redraw
        the figure without refitting.
        ``fit_results[qubit]`` — a compact scalar summary (success flag, number
        of fitted flux points, centre-frequency span) used for logging / outcomes.
    """
    from scqat.parsers import repetition_data
    from scqat.protocols.resonator_spectroscopy_vs_flux import ResonatorSpectroscopyVsFluxAnalyzer

    analyzer = ResonatorSpectroscopyVsFluxAnalyzer()
    sep_results: Dict = {}
    fit_results: Dict = {}
    n_sigma = float(getattr(node.parameters, "outlier_n_sigma", 3.0))

    for sq in repetition_data(ds, repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        results = analyzer.analyze(sq, output_dir=None, skip_figures=True, n_sigma=n_sigma)[0]
        sep_results[qubit_name] = (sq, results)

        # Centre-frequency span computed over the kept (good) points only.
        trace = np.asarray(results.get("center_full_freq", results["center_detuning"]), dtype=float)
        good = np.asarray(results["good"], dtype=bool)
        trace_good = trace[good]
        any_good = trace_good.size > 0 and bool(np.isfinite(trace_good).any())
        fit_results[qubit_name] = {
            "success": bool(results["n_good"] > 0),
            "n_success": int(results["n_success"]),
            "n_good": int(results["n_good"]),
            "n_outlier": int(results["n_outlier"]),
            "n_flux": int(results["n_flux"]),
            "center_freq_min": float(np.nanmin(trace_good)) if any_good else float("nan"),
            "center_freq_max": float(np.nanmax(trace_good)) if any_good else float("nan"),
            "has_full_freq": "center_full_freq" in results,
        }

    return sep_results, fit_results


def log_fitted_results(fit_results: Dict, log_callable=None) -> None:
    """Log a per-qubit summary of the flux-by-flux dip fit."""
    if log_callable is None:
        log_callable = logging.getLogger(__name__).info
    for q, fr in fit_results.items():
        s = (
            f"Results for qubit {q}: "
            f"kept {fr['n_good']}/{fr['n_flux']} flux points "
            f"({fr['n_success']} in-window, {fr['n_outlier']} outliers) | "
            f"resonator centre {1e-9 * fr['center_freq_min']:.3f} to {1e-9 * fr['center_freq_max']:.3f} GHz | "
            f"{'SUCCESS!' if fr['success'] else 'FAIL!'}"
        )
        log_callable(s)


def fit_flux_dependence(sep_results: Dict, node: QualibrationNode) -> Tuple[Dict, Dict]:
    """Fit each qubit's ``center_frequency(flux)`` trace with the scqat
    ``ResonatorFluxDispersionAnalyzer`` (full-transmon dispersive model).

    Consumes the per-qubit ``(slice_ds, vs_flux_results)`` pairs from
    ``fit_raw_data`` and runs the dispersion fit on the extracted centre trace.

    Returns
    -------
    (dispersion_sep, dispersion_results)
        ``dispersion_sep[qubit] = (trace_ds, analyzer_results)`` kept for redraw;
        ``dispersion_results[qubit]`` is a compact scalar summary (sweet spot,
        period dv_phi0, f_r0, conditional g, ...). ``g`` is conditional on the
        assumed ``f_q_max`` until a spectroscopy prior is wired in.
    """
    from scqat.protocols.resonator_flux_dispersion import ResonatorFluxDispersionAnalyzer

    analyzer = ResonatorFluxDispersionAnalyzer()
    dispersion_sep: Dict = {}
    dispersion_results: Dict = {}

    for qubit_name, (sq, results) in sep_results.items():
        center = np.asarray(results.get("center_full_freq", results["center_detuning"]), dtype=float)
        # Feed only the truncated (good) points — in-window fits with non-outlier
        # width/amplitude — to the frequency-vs-flux dispersive fit.
        trace = xr.Dataset(
            {
                "center_freq": ("flux_bias", center),
                "success": ("flux_bias", np.asarray(results["good"], dtype=bool)),
            },
            coords={"flux_bias": np.asarray(results["flux_bias"], dtype=float)},
        )
        # NOTE: an f_q_max prior (from qubit spectroscopy / the QUAM state) could
        # be passed here to make g physical; deferred for now (g stays conditional).
        res = analyzer.analyze(trace, output_dir=None, skip_figures=True)[0]
        dispersion_sep[qubit_name] = (trace, res)

        # Instrument/state-level conversions (kept out of the physics analyzer):
        # the minimum-frequency flux point sits half a period from the sweet spot
        # (toward 0, clamped to the line range), and the flux quantum in current.
        sweet = float(res["sweet_spot_flux"])
        dv = float(res["dv_phi0"])
        min_offset = float("nan")
        if np.isfinite(sweet) and np.isfinite(dv) and dv > 0:
            direction = 0.5 if sweet < 0 else -0.5
            min_offset = float(np.clip(sweet + direction * dv, -0.5, 0.5))
        phi0_current = float("nan")
        if node is not None and np.isfinite(dv):
            attenuation_factor = 10 ** (-node.parameters.line_attenuation_in_db / 20)
            phi0_current = float(dv * node.parameters.input_line_impedance_in_ohm * attenuation_factor)

        dispersion_results[qubit_name] = {
            "success": bool(res["success"]),
            "sweet_spot_flux": sweet,
            "sweet_spot_freq": float(res["sweet_spot_freq"]),
            "min_offset": min_offset,
            "dv_phi0": dv,
            "phi0_current": phi0_current,
            "f_r0": float(res["f_r0"]),
            "g": float(res["g"]),
            "f_q_max": float(res["f_q_max"]),
            "f_q_max_fixed": bool(res["f_q_max_fixed"]),
            "n_points": int(res["n_points"]),
        }

    return dispersion_sep, dispersion_results


def log_dispersion_results(dispersion_results: Dict, log_callable=None) -> None:
    """Log a per-qubit summary of the dispersive flux-dependence fit."""
    if log_callable is None:
        log_callable = logging.getLogger(__name__).info
    for q, r in dispersion_results.items():
        cond = " (g conditional on assumed f_q_max)" if r["f_q_max_fixed"] else ""
        s = (
            f"Flux dispersion {q}: "
            f"sweet spot @ {r['sweet_spot_flux'] * 1e3:.1f} mV, {1e-9 * r['sweet_spot_freq']:.4f} GHz | "
            f"min offset @ {r['min_offset'] * 1e3:.1f} mV | "
            f"dv_phi0 = {r['dv_phi0']:.4f} V | f_r0 = {1e-9 * r['f_r0']:.4f} GHz | "
            f"g = {1e-6 * r['g']:.1f} MHz{cond} | "
            f"{'SUCCESS!' if r['success'] else 'FAIL!'}"
        )
        log_callable(s)
