"""N-swap (swap-chain) estimate adapter: adapts the raw dataset and delegates to scqat.

The estimator (cosine fit of population vs the number of swaps N) returns the
swap-oscillation frequency `f` (cycles per swap), `swap_period` (swaps per full
population cycle) and a `success` flag, which the shell's outcome gating consumes.
There is no state writeback — the extracted quantities are for inspection only.
"""

from typing import Dict, Tuple

import xarray as xr


def fit(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Tuple[Dict, Dict]:
    """Fit each measured qubit's swap oscillation with scqat's SwapOscillationEstimator.

    Returns (fit_results, figures), both keyed by qubit name. `fit_results` holds the
    estimator's full `results` (including `success`).
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.swap_oscillation import SwapOscillationEstimator

    if use_state_discrimination:
        ds = ds_raw.rename({"state": "signal"})
    else:
        ds = ds_raw.rename({"I": "signal"})

    sep_data = repetition_data(ds, repetition_dim="qubit")
    fit_results: Dict = {}
    figures: Dict = {}
    estimator = SwapOscillationEstimator()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        results, figs = estimator.analyze(sq_data, output_dir=None)
        fit_results[qubit_name] = results
        figures[qubit_name] = figs
    return fit_results, figures
