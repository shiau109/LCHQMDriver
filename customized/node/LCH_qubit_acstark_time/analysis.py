"""Time-dependent readout-resonator photon estimate adapter.

Wraps scqat's :class:`ReadoutPulsePhotonEstimator` ("qubit spectroscopy vs delay"):
for each delay slice it locates the AC-Stark-shifted qubit line and turns the trace
into a photon-number-vs-time curve (resonator filling / ring-down). The estimator
expects the raw I/Q (it builds ``IQdata = I + 1j*Q``) plus the ``detuning`` and
``delay_time`` coordinates the probe emits, so this path applies when
``use_state_discrimination=False``.

Following the import rule, scqat is imported lazily inside :func:`estimate` so the
node module stays importable without the analysis package installed.
"""

from typing import Dict, Tuple

import xarray as xr


def estimate(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Tuple[Dict, Dict]:
    """Run the readout-pulse-photon estimator per qubit.

    Returns ``(fit_results, figures)`` keyed by qubit name. Each ``fit_results``
    entry is the estimator's results dict (e.g. ``peak_detuning`` / ``photon_number``
    / ``delay_times``) augmented with a ``success`` flag for ``node.outcomes``.

    ``use_state_discrimination`` is accepted for interface symmetry; the estimator
    needs raw I/Q, so callers should acquire with it set to ``False``.
    """
    from scqat.parsers import repetition_data
    from scqat.estimators.readout_pulse_photon import ReadoutPulsePhotonEstimator

    fit_results: Dict = {}
    figures: Dict = {}
    estimator = ReadoutPulsePhotonEstimator()
    for sq_data in repetition_data(ds_raw):
        qubit_name = sq_data["qubit"].values.item()
        print(f"Analysing {qubit_name}.")
        results, figs = estimator.analyze(sq_data, output_dir=None)
        results.setdefault("success", True)
        fit_results[qubit_name] = results
        figures[qubit_name] = figs
    return fit_results, figures
