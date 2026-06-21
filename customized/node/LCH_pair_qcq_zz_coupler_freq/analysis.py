"""Analysis for LCH_pair_qcq_zz_coupler_freq: residual ZZ coupling vs coupler frequency.

Each coupler-flux slice is a Ramsey-like decaying oscillation of the measured-qubit ``signal`` vs
interaction time, so the per-slice fit is delegated to scqat's :class:`RamseyEstimator`
(``scqat.estimators.ramsey``) — they are the same fit. For each coupler bias the estimator returns
the fringe frequency ``f_1`` and decay time ``tau_1``; we store:

    jeff_raw   = f_1                       [MHz]  (the positive fringe frequency = |ζ + ωb|)
    zz_raw     = f_1 − virtual_detuning    [MHz]  (the **signed** residual ZZ coupling ζ)
    period_raw = 1 / f_1                   [µs]   (the fringe period; NaN where unresolved)
    tau_raw    = tau_1                      [µs]
    fit_mask                                       (slice fit succeeded with a resolvable frequency)

The Ramsey fit only resolves the magnitude of the fringe frequency, so the **sign** of ζ is
recovered the same way ``LCH_Ramsey`` recovers the qubit detuning (``update.compute_update``:
``d_f01 = f_1 − detuning``): ζ = f_1 − virtual_detuning. This is valid while the virtual detuning ωb
dominates (ωb > |ζ|), so the true fringe frequency f = ζ + ωb stays positive and equals the measured
|f|. The ZZ-off coupler bias is where ζ crosses zero (read off the ``zz_vs_coupler`` figure — this
node performs no automated state writeback).

The signal that is fit is the measured qubit's marginal, built in :func:`process_raw_dataset`:
state discrimination -> P(measured qubit = excited); IQ readout -> its ``I`` quadrature.
"""

import logging
from dataclasses import dataclass
from typing import Dict, Tuple

import numpy as np
import xarray as xr
from qualibrate import QualibrationNode


@dataclass
class FitResults:
    """Stores the relevant ZZ-vs-coupler-frequency fit parameters for a single qubit pair."""

    max_decay_time: float  # maximum decay time constant (tau = 1/kappa) in µs
    max_decay_time_amplitude: float  # coupler bias amplitude where max decay time occurs
    success: bool


def log_fitted_results(fit_results: Dict[str, FitResults], log_callable=None):
    """
    Logs the ZZ-vs-coupler-frequency fitted results for all qubit pairs.

    Parameters:
    -----------
    fit_results : Dict[str, FitResults]
        Dictionary containing FitResults for each qubit pair.
    log_callable : callable, optional
        Logger for logging the fitted results. If None, a default logger is used.
    """
    if log_callable is None:
        log_callable = logging.getLogger(__name__).info

    for qp_name, fit_result in fit_results.items():
        s_qubit = f"Results for qubit pair {qp_name}: "
        s_tau = (
            f"\tMaximum decay time constant: {fit_result.max_decay_time:.6f} µs "
            f"at coupler bias {fit_result.max_decay_time_amplitude:.6f} V"
        )

        if fit_result.success:
            s_qubit += "SUCCESS!\n"
        else:
            s_qubit += "FAIL!\n"

        log_message = s_qubit + s_tau

        log_callable(log_message)


def process_raw_dataset(ds: xr.Dataset, node: QualibrationNode):
    """
    Process the raw dataset for ZZ-vs-coupler-frequency analysis.

    Both qubits of the pair are acquired. This builds the canonical ``signal`` variable that the
    Ramsey fit oscillates against: the **measured** qubit's excited-state population (state
    discrimination, reconstructed as a marginal of the joint populations) or its ``I`` quadrature
    (IQ readout).

    Parameters:
    -----------
    ds : xr.Dataset
        Raw dataset from the experiment
    node : QualibrationNode
        The calibration node containing qubit pairs information

    Returns:
    --------
    xr.Dataset
        Processed dataset with ``time_us`` coord and the ``signal`` variable
    """
    # Convert time from ns to µs for fitting (Ramsey estimator works in µs -> f in MHz)
    time_us = ds.time.data * 1e-3
    ds = ds.assign_coords(time_us=("time", time_us))

    # Reconstruct the measured-qubit signal the fit uses (marginal over the partner qubit).
    measure = node.parameters.measure_qubit
    if "state_gg" in ds.data_vars:
        # Joint populations present (first digit = control, second = target).
        #   P(control = excited) = P10 + P11 = state_eg + state_ee
        #   P(target  = excited) = P01 + P11 = state_ge + state_ee
        signal = ds["state_eg"] + ds["state_ee"] if measure == "control" else ds["state_ge"] + ds["state_ee"]
    else:
        signal = ds["I_control"] if measure == "control" else ds["I_target"]
    ds["signal"] = signal
    ds["signal"].attrs = {"long_name": f"measured ({measure}) qubit signal", "units": "a.u."}

    return ds


def fit_raw_data(ds: xr.Dataset, node: QualibrationNode) -> Tuple[xr.Dataset, Dict[str, FitResults]]:
    """
    Fit each coupler-flux slice with scqat's Ramsey estimator and extract ZZ vs coupler frequency.

    Parameters:
    -----------
    ds : xr.Dataset
        Dataset containing the processed data (must carry ``signal`` + ``time_us``).
    node : QualibrationNode
        The calibration node containing parameters and qubit pairs.

    Returns:
    --------
    Tuple[xr.Dataset, Dict[str, FitResults]]
        Dataset with fit results and dictionary of fit results for each qubit pair.
    """
    # Lazy import: probes/nodes never import scqat at module load (kept out of the acquisition path).
    from scqat.estimators.ramsey import RamseyEstimator

    estimator = RamseyEstimator()
    ds_fit = ds.groupby("qubit_pair").apply(lambda da: fit_zz_slices(da, node, estimator))

    # Extract the relevant fitted parameters
    ds_fit, fit_results = _extract_relevant_parameters(ds_fit, node)

    return ds_fit, fit_results


def fit_zz_slices(da: xr.DataArray, node: QualibrationNode, estimator) -> xr.DataArray:
    """
    Fit the measured-qubit oscillation vs time for each coupler bias with the Ramsey estimator.

    Parameters:
    -----------
    da : xr.DataArray
        Data (one qubit pair) carrying ``signal`` (dims amp x time) and the ``time_us`` coord.
    node : QualibrationNode
        The calibration node containing parameters.
    estimator : RamseyEstimator
        The scqat Ramsey estimator instance.

    Returns:
    --------
    xr.DataArray
        Data with the per-bias fit results added along ``amp``.
    """
    signal_da = da["signal"].squeeze()
    data_matrix = signal_da.transpose("time", "amp").values  # shape = (n_time, n_amp)
    flux_bias = da.amp.data  # coupler bias amplitude values (tune the coupler frequency)
    time_us = da.time_us.data  # interaction time [µs] (the Ramsey idle axis)

    n_amp = data_matrix.shape[1]
    jeff_raw = np.zeros(n_amp)  # f_1 [MHz] = ζ + ωb
    tau_raw = np.full(n_amp, np.nan)  # T2* [µs]
    period_raw = np.full(n_amp, np.nan)  # 1/f_1 [µs]
    fit_mask = np.zeros(n_amp, dtype=bool)

    for i in range(n_amp):
        slice_ds = xr.Dataset(
            {"signal": ("idle_time", data_matrix[:, i])},
            coords={"idle_time": time_us},
        )
        try:
            res = estimator.extract_parameters(slice_ds)
        except Exception:  # pylint: disable=broad-except
            continue
        freq = abs(float(res.get("f_1", 0.0) or 0.0))  # the Ramsey fringe frequency [MHz]
        resolved = bool(res.get("success", False)) and freq > 0 and res.get("model_type") != "relaxation"
        jeff_raw[i] = freq
        tau_raw[i] = float(res.get("tau_1", np.nan))
        if resolved:
            period_raw[i] = 1.0 / freq
            fit_mask[i] = True

    # Diagnostics: success if any coupler-flux slice yielded a resolvable Ramsey fringe.
    valid = np.where(fit_mask)[0]
    if valid.size:
        tau_valid = np.where(fit_mask & np.isfinite(tau_raw) & (tau_raw > 0))[0]
        if tau_valid.size:
            mt_idx = tau_valid[np.argmax(tau_raw[tau_valid])]
            max_decay_time = float(tau_raw[mt_idx])
            max_decay_time_amplitude = float(flux_bias[mt_idx])
        else:
            max_decay_time = np.nan
            max_decay_time_amplitude = np.nan
        success = True
    else:
        max_decay_time = np.nan
        max_decay_time_amplitude = np.nan
        success = False

    da = da.assign(
        jeff_raw=("amp", jeff_raw),
        period_raw=("amp", period_raw),
        tau_raw=("amp", tau_raw),
        fit_mask=("amp", fit_mask),
        max_decay_time=max_decay_time,
        max_decay_time_amplitude=max_decay_time_amplitude,
        success=success,
    )

    return da


def _extract_relevant_parameters(
    ds_fit: xr.Dataset, node: QualibrationNode
) -> Tuple[xr.Dataset, Dict[str, FitResults]]:
    """
    Add metadata to the fitted dataset and build FitResults for each qubit pair.

    Parameters:
    -----------
    ds_fit : xr.Dataset
        Dataset containing the per-bias fit results from fit_zz_slices.
    node : QualibrationNode
        The calibration node containing parameters and qubit pairs.

    Returns:
    --------
    Tuple[xr.Dataset, Dict[str, FitResults]]
        Dataset with metadata and dictionary of FitResults for each qubit pair.
    """
    qubit_pairs = node.namespace["qubit_pairs"]

    if "max_decay_time" in ds_fit.data_vars:
        ds_fit.max_decay_time.attrs = {"long_name": "maximum decay time constant", "units": "µs"}
    if "max_decay_time_amplitude" in ds_fit.data_vars:
        ds_fit.max_decay_time_amplitude.attrs = {"long_name": "coupler bias at maximum decay time", "units": "V"}
    ds_fit["virtual_detuning"] = node.parameters.virtual_detuning_in_mhz
    if "jeff_raw" in ds_fit.data_vars:
        # Signed residual ZZ: ζ = f − ωb (sign recovered against the known virtual detuning).
        ds_fit["zz_raw"] = ds_fit["jeff_raw"] - node.parameters.virtual_detuning_in_mhz
        ds_fit.zz_raw.attrs = {"long_name": "residual ZZ coupling ζ = f − ωb (signed)", "units": "MHz"}
        ds_fit.jeff_raw.attrs = {"long_name": "Ramsey fringe frequency |ζ + ωb|", "units": "MHz"}
    if "period_raw" in ds_fit.data_vars:
        ds_fit.period_raw.attrs = {"long_name": "Ramsey period (1/f)", "units": "µs"}
    if "tau_raw" in ds_fit.data_vars:
        ds_fit.tau_raw.attrs = {"long_name": "decay time constant T2*", "units": "µs"}
    if "fit_mask" in ds_fit.data_vars:
        ds_fit.fit_mask.attrs = {"long_name": "successful Ramsey fit mask", "units": "bool"}

    fit_results = {}
    for qp in qubit_pairs:
        qp_name = qp.name
        qp_data = ds_fit.sel(qubit_pair=qp_name)
        fit_results[qp_name] = FitResults(
            max_decay_time=float(qp_data.max_decay_time.values),
            max_decay_time_amplitude=float(qp_data.max_decay_time_amplitude.values),
            success=bool(qp_data.success.values),
        )

    return ds_fit, fit_results
