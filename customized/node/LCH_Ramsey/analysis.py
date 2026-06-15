"""Ramsey estimate adapter: adapts the raw dataset and delegates to scqat.

The estimator selects the model (single damped sine / two-frequency beat /
pure relaxation) and returns `model_type` plus `f_1` (and `f_2` for the beat
case), which `update.compute_update` consumes.
"""

from typing import Dict, Tuple

import xarray as xr


def fit(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Tuple[Dict, Dict]:
    """Fit each qubit's Ramsey fringe with scqat's RamseyEstimator.

    Returns (fit_results, figures), both keyed by qubit name. `fit_results`
    holds only the scalar fit params (`extract_metadata`); dropping the
    estimator's diagnostic arrays (best_fit/fft_freq/fft_amp) keeps
    arrays.npz from being written by the shell.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.ramsey import RamseyEstimator

    if use_state_discrimination:
        ds = ds_raw.rename({"state": "signal"})
    else:
        ds = ds_raw.rename({"I": "signal"})

    sep_data = repetition_data(ds, repetition_dim="qubit")
    fit_results: Dict = {}
    figures: Dict = {}
    estimator = RamseyEstimator()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        results, figs = estimator.analyze(sq_data, output_dir=None)
        fit_results[qubit_name] = estimator.extract_metadata(results)
        figures[qubit_name] = figs
    return fit_results, figures
