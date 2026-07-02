"""N-swap x qubit-flux-amplitude estimate adapter: adapts the raw dataset and delegates
to scqat, fitting the swap oscillation at EVERY amplitude row.

For each measured qubit and each swept ctrl flux amplitude, the population-vs-N curve is
fit with a cosine (scqat SwapOscillationEstimator, figures skipped per row), giving the
swap-oscillation frequency `f` (cycles per swap), its contrast `a` and
`swap_period = 1/f` versus amplitude. A qubit's outcome is successful when at least one
row fit succeeds; `best_amplitude` -- the successful row with the largest contrast `a`
-- is reported for inspection only, there is no state writeback. Contrast (not `f`)
marks the swap resonance: a detuned swap oscillates FASTER (generalized Rabi) but
shallower, and contrast is also robust to noise-only rows that slip past the fit gate
with a spurious frequency.
"""

from typing import Dict, Tuple

import numpy as np
import xarray as xr

from . import plotting


def fit(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Tuple[Dict, Dict]:
    """Fit each qubit's swap oscillation at every amplitude with scqat.

    Returns (fit_results, figures), both keyed by qubit name. `fit_results[qubit]` holds
    per-row arrays (`amplitudes`, `f`, `a`, `swap_period`, `r_squared`, `row_success`)
    plus the aggregate `success` flag and `best_amplitude` (largest-contrast row).
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
        amplitudes = np.asarray(sq_data["qubit_amplitude"].values, dtype=float)

        f = np.full(amplitudes.size, np.nan)
        a = np.full(amplitudes.size, np.nan)
        swap_period = np.full(amplitudes.size, np.nan)
        r_squared = np.full(amplitudes.size, np.nan)
        row_success = np.zeros(amplitudes.size, dtype=bool)
        for i in range(amplitudes.size):
            row = sq_data.isel(qubit_amplitude=i)
            results, _ = estimator.analyze(row, output_dir=None, skip_figures=True)
            f[i] = results["f"]
            a[i] = results["a"]
            swap_period[i] = results["swap_period"]
            r_squared[i] = results["r_squared"]
            row_success[i] = bool(results["success"])

        # The swap resonance: the trusted row with the deepest population exchange. A
        # detuned swap oscillates faster but shallower, so contrast (not f) marks it.
        best_amplitude = float(amplitudes[np.nanargmax(np.where(row_success, a, -np.inf))]) if row_success.any() else None

        fit_results[qubit_name] = {
            "success": bool(row_success.any()),
            "amplitudes": amplitudes.tolist(),
            "f": f.tolist(),
            "a": a.tolist(),
            "swap_period": swap_period.tolist(),
            "r_squared": r_squared.tolist(),
            "row_success": row_success.tolist(),
            "best_amplitude": best_amplitude,
        }
        figures[qubit_name] = plotting.plot_amp_rounds_2d(
            sq_data,
            fit_results[qubit_name],
            qubit_name=qubit_name,
            use_state_discrimination=use_state_discrimination,
        )
    return fit_results, figures
