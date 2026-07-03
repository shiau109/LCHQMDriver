"""Resonator-spectroscopy-vs-power estimate adapter: adapts the raw dataset and
delegates to scqat.

Fitting and figure generation are split (`fit` with skip_figures, then `figures`)
so the shell keeps qualibrate's analyse-now/plot-later flow and the fit runs once.
The estimator collapses the 2-D ``(power, detuning)`` map to a 1-D
``center_frequency(power)`` trace (single inverted Lorentzian per power slice) and
picks the optimal readout power; `fit` needs the qubit objects to attach the
absolute ``full_freq`` axis the estimator reports the resonance frequency on.

scqat is imported lazily (only inside the fit call) so the node still imports
without scqat installed; the official nodes never need it.
"""

from typing import Dict, Tuple

import xarray as xr


def fit(ds_raw: xr.Dataset, qubits, **analyze_kwargs) -> Tuple[Dict, Dict, object]:
    """Fit each qubit's resonator-vs-power map with scqat's
    ``ResonatorSpectroscopyPowerEstimator``.

    `ds_raw` carries I/Q and the qubit/detuning/power coords. `analyze_kwargs`
    (``n_sigma`` and the derivative-pick tuning params) are forwarded to the
    estimator. Returns (fit_results, sep_results, estimator):
      * fit_results[qubit] = {"optimal_power", "frequency_shift", "resonator_frequency",
        "success", "n_good", "n_power"} - JSON-friendly, what the shell persists and
        `update` consumes;
      * sep_results[qubit] = (per-qubit dataset, full estimator results) - for
        deferred figure drawing;
      * estimator - the instance to pass back to `figures`.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.resonator_spectroscopy_power import ResonatorSpectroscopyPowerEstimator

    estimator = ResonatorSpectroscopyPowerEstimator()
    fit_results: Dict = {}
    sep_results: Dict = {}

    for sq in repetition_data(ds_raw, repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        q = next(x for x in qubits if x.name == qubit_name)
        # Add the absolute readout-frequency axis so the estimator can report the
        # resonator frequency at the optimal power.
        sq = sq.assign_coords(full_freq=("detuning", (sq.detuning + q.resonator.RF_frequency).values))
        results = estimator.analyze(sq, output_dir=None, skip_figures=True, **analyze_kwargs)[0]
        fit_results[qubit_name] = {
            "optimal_power": float(results["optimal_power"]),
            "frequency_shift": float(results["frequency_shift"]),
            "resonator_frequency": float(results["resonator_frequency"]),
            "success": bool(results["optimal_success"]),
            "n_good": int(results["n_good"]),
            "n_power": int(results["n_power"]),
        }
        sep_results[qubit_name] = (sq, results)

    return fit_results, sep_results, estimator


def figures(estimator, sep_results: Dict) -> Dict:
    """Draw the scqat resonator-spectroscopy-vs-power figures from the stored
    (dataset, results) pairs."""
    return {
        qubit_name: estimator.generate_figures(sq, results)
        for qubit_name, (sq, results) in sep_results.items()
    }
