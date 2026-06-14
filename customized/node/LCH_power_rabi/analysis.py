"""Power-Rabi estimate adapter: adapts the raw dataset and delegates to scqat.

The estimator (cosine fit) returns `opt_amp_prefactor` (the multiplier on the
current pulse amplitude that yields a pi pulse) and a `success` flag, which
`update.compute_update` and the shell's outcome gating consume.
"""

from typing import Dict, Tuple

import xarray as xr


def fit(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Tuple[Dict, Dict]:
    """Fit each qubit's power-Rabi cosine with scqat's PowerRabiEstimator.

    Returns (fit_results, figures), both keyed by qubit name. `fit_results`
    holds the estimator's full `results` (including `success`), as the node
    persisted historically.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.power_rabi import PowerRabiEstimator

    if use_state_discrimination:
        ds = ds_raw.rename({"state": "signal"})
    else:
        ds = ds_raw.rename({"I": "signal"})

    sep_data = repetition_data(ds, repetition_dim="qubit")
    fit_results: Dict = {}
    figures: Dict = {}
    estimator = PowerRabiEstimator()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        results, figs = estimator.analyze(sq_data, output_dir=None)
        fit_results[qubit_name] = results
        figures[qubit_name] = figs
    return fit_results, figures
