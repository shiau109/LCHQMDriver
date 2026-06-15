"""Resonator-spectroscopy estimate adapter: adapts the raw dataset and delegates to scqat.

Fitting and figure generation are split (`fit` with skip_figures, then `figures`)
so the shell keeps qualibrate's analyse-now/plot-later flow and the fit runs once.
The estimator fits a single inverted Lorentzian to the |IQ| amplitude dip; `fit`
needs the qubit objects to attach the absolute `full_freq` axis the estimator
reports the resonance frequency on.
"""

from typing import Dict, Tuple

import xarray as xr


def fit(ds_raw: xr.Dataset, qubits) -> Tuple[Dict, Dict, object]:
    """Fit each qubit's resonator dip with scqat's ResonatorSpectroscopyEstimator.

    `ds_raw` carries I/Q and the qubit/detuning coords. Returns
    (fit_results, sep_results, estimator):
      * fit_results[qubit] = {"frequency", "fwhm", "success"} - JSON-friendly;
      * sep_results[qubit] = (per-qubit dataset, full estimator results) - for
        deferred figure drawing;
      * estimator - the instance to pass back to `figures`.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.resonator_spectroscopy import ResonatorSpectroscopyEstimator

    estimator = ResonatorSpectroscopyEstimator()
    fit_results: Dict = {}
    sep_results: Dict = {}

    for sq in repetition_data(ds_raw, repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        q = next(x for x in qubits if x.name == qubit_name)
        # Add the absolute readout-frequency axis so the estimator can report f_01
        sq = sq.assign_coords(full_freq=("detuning", (sq.detuning + q.resonator.RF_frequency).values))
        results = estimator.analyze(sq, output_dir=None, skip_figures=True)[0]
        # scqat reports full_freq when the coord is present; fall back to detuning + RF
        frequency = float(results.get("full_freq", results["detuning"] + q.resonator.RF_frequency))
        fit_results[qubit_name] = {
            "frequency": frequency,
            "fwhm": float(results["fwhm"]),
            "success": bool(results["success"]),
        }
        sep_results[qubit_name] = (sq, results)

    return fit_results, sep_results, estimator


def figures(estimator, sep_results: Dict) -> Dict:
    """Draw the scqat resonator-spectroscopy figures from the stored (dataset, results) pairs."""
    return {
        qubit_name: estimator.generate_figures(sq, results)
        for qubit_name, (sq, results) in sep_results.items()
    }
