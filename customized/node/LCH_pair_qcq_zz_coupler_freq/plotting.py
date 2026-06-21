"""Plotting for LCH_pair_qcq_zz_coupler_freq: residual ZZ coupling vs coupler frequency.

The per-bias fit uses scqat's Ramsey estimator, so each coupler-flux slice yields a fringe
frequency ``jeff_raw`` (= ζ + ωb), a period ``period_raw`` (= 1/f), and a decay time ``tau_raw``.
The swept axis (``amp`` [V]) is the coupler bias amplitude that **tunes the coupler frequency** via
the gated ``const`` flux pulse.

Both qubits of the pair are acquired; :func:`plot_joint_states` shows the joint populations
(P00/P01/P10/P11) or both qubits' I/Q, while the residual-ZZ / period / decay plots operate on the
measured-qubit ``signal``.
"""

from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from matplotlib.figure import Figure
from qualibration_libs.plotting import grid_iter

from .pair_grid import QubitPairGrid, grid_pair_names

# Joint-population variable -> display label (first digit = control, second = target).
_JOINT_PANELS = [
    ("state_gg", "00"),
    ("state_ge", "01"),
    ("state_eg", "10"),
    ("state_ee", "11"),
]

_XLABEL = "Coupler bias (V) — tunes coupler frequency"


def _subplot_title(ds: xr.Dataset, qp_name: str) -> str:
    if "measured_qubit_name" in ds.coords:
        measured_name = str(ds.measured_qubit_name.sel(qubit_pair=qp_name).values)
        return f"{qp_name}\nMeasured: {measured_name}"
    return qp_name


def _pairs_with_successful_fits(ds_fit: xr.Dataset, qubit_pairs) -> list:
    return [qp for qp in qubit_pairs if bool(ds_fit.sel(qubit_pair=qp.name).success.values)]


def plot_zz_vs_coupler(ds_fit: xr.Dataset, qubit_pairs) -> Figure | None:
    """Signed residual ZZ coupling ζ vs coupler bias (frequency) for each pair, with a twin y-axis.

    ``zz_raw`` = f − ωb is the **signed** residual ZZ: the sign is recovered against the known
    virtual detuning ωb (see analysis), so the curve can go negative or positive and crosses zero
    at the ZZ-off coupler bias (marked with the dashed ζ = 0 line). The left y-axis reads the
    residual ZZ ζ; the right y-axis reads the fringe frequency f = ζ + ωb (the same curve on a scale
    shifted by ωb). Only slices with a resolvable Ramsey fringe (``fit_mask``) are shown; pairs with
    no successful fit are skipped.

    Returns a Figure, or ``None`` if there is nothing to plot.
    """
    valid_pairs = _pairs_with_successful_fits(ds_fit, qubit_pairs)
    if not valid_pairs:
        return None

    virtual_detuning = float(ds_fit.virtual_detuning)
    g_names, qp_names = grid_pair_names(valid_pairs)
    grid = QubitPairGrid(g_names, qp_names)
    for ax, qubit in grid_iter(grid):
        qp_name = qubit["qubit"]
        fit_result = ds_fit.sel(qubit_pair=qp_name)
        fit_mask = fit_result.fit_mask.values.astype(bool)
        flux_plot = fit_result.amp.values[fit_mask]
        zz = fit_result.zz_raw.values[fit_mask]  # signed ζ = f − ωb

        ax.plot(flux_plot, zz, "o-", color="orange", label="Residual ZZ ζ")
        ax.axhline(0.0, color="red", linestyle="--", linewidth=1.5, label="ZZ-off (ζ = 0)")

        # Right y-axis = fringe frequency f = ζ + ωb (linked transform, stays in sync with the left).
        secax = ax.secondary_yaxis(
            "right",
            functions=(lambda z, d=virtual_detuning: z + d, lambda f, d=virtual_detuning: f - d),
        )
        secax.set_ylabel("Fringe frequency f = ζ + ωb (MHz)")

        ax.set_title(_subplot_title(ds_fit, qp_name))
        ax.set_xlabel(_XLABEL)
        ax.set_ylabel("Residual ZZ ζ (MHz)")
        ax.grid(True)
        ax.legend(fontsize="small")

    grid.fig.tight_layout()
    return grid.fig


def plot_decay_rate_data(ds_fit: xr.Dataset, qubit_pairs, log_y: bool = False) -> Figure | None:
    """Decay time constant τ (= T2*) vs coupler bias (frequency) for each pair.

    Uses the Ramsey-extracted ``tau_raw``. Pairs with no valid decay-time extraction are skipped;
    returns ``None`` if there is nothing to plot.
    """
    valid_pairs = [qp for qp in qubit_pairs if np.any(ds_fit.sel(qubit_pair=qp.name).tau_raw.values > 0)]
    if not valid_pairs:
        return None

    g_names, qp_names = grid_pair_names(valid_pairs)
    grid = QubitPairGrid(g_names, qp_names)
    for ax, qubit in grid_iter(grid):
        qp_name = qubit["qubit"]
        fit_result = ds_fit.sel(qubit_pair=qp_name)
        fit_mask = fit_result.fit_mask.values.astype(bool)
        tau_raw = fit_result.tau_raw.values
        valid_tau_mask = fit_mask & np.isfinite(tau_raw) & (tau_raw > 0)
        flux_plot = fit_result.amp.values[valid_tau_mask]
        tau_plot = tau_raw[valid_tau_mask]

        ax.plot(flux_plot, tau_plot, "o-", color="teal", label="Decay time T2*")
        if log_y:
            ax.set_yscale("log")

        if not np.isnan(fit_result.max_decay_time.values):
            max_tau = fit_result.max_decay_time.values
            max_tau_amp = fit_result.max_decay_time_amplitude.values
            if not log_y or max_tau > 0:
                ax.plot(max_tau_amp, max_tau, "ro", markersize=8, label=f"Max τ ({max_tau:.3f} µs)")

        ax.set_title(_subplot_title(ds_fit, qp_name))
        ax.set_xlabel(_XLABEL)
        ax.set_ylabel("Decay time constant τ (µs)")
        ax.grid(True, which="both" if log_y else "major")
        ax.legend(fontsize="small")

    grid.fig.tight_layout()
    return grid.fig


def plot_raw_data(ds_fit: xr.Dataset, qubit_pairs) -> Figure:
    """2D heatmap of the measured-qubit ``signal`` vs (coupler bias, time), with the fitted
    Ramsey period overlaid per coupler-flux slice.

    The heatmap shows the bright/dark fringes of the canonical ``signal`` (the measured qubit's
    marginal the Ramsey fit oscillates against, built in ``process_raw_dataset``). On top, the
    fitted period ``period_raw`` = 1/f is drawn as markers (converted µs -> ns) for every slice
    where the Ramsey fit resolved a frequency, so the fitted points can be checked directly against
    the fringe spacing.

    A horizontal reference line marks 1/(virtual detuning) — the fringe period expected at ZZ = 0
    (f = ωb). Where the fitted-period markers cross this line is the ZZ-off coupler bias.

    Pass the **fitted** dataset (``ds_fit``): it carries ``signal``, ``period_raw`` / ``fit_mask``
    and ``virtual_detuning``.
    """
    virtual_detuning = float(ds_fit.virtual_detuning)
    detuning_period_ns = 1e3 / virtual_detuning if virtual_detuning else np.nan  # 1/ωb [µs] -> ns

    g_names, qp_names = grid_pair_names(qubit_pairs)
    grid = QubitPairGrid(g_names, qp_names)
    for ax, qubit in grid_iter(grid):
        qp_name = qubit["qubit"]
        fit_result = ds_fit.sel(qubit_pair=qp_name)
        fit_result["signal"].squeeze().plot(ax=ax, x="amp", y="time")
        # Keep the heatmap's time range; overlaid period points outside it are clipped.
        ylim = ax.get_ylim()

        mask = fit_result.fit_mask.values.astype(bool)
        if mask.any():
            period_ns = fit_result.period_raw.values[mask] * 1e3  # µs -> ns to match the time axis
            ax.plot(fit_result.amp.values[mask], period_ns, "o-", color="white",
                    markeredgecolor="black", linewidth=1, markersize=5, label="Fitted period 1/f")
        if np.isfinite(detuning_period_ns):
            ax.axhline(detuning_period_ns, color="red", linestyle="--", linewidth=1.5,
                       label=f"1/virtual detuning ({detuning_period_ns:.0f} ns)")
        ax.set_ylim(ylim)

        ax.set_xlabel(_XLABEL)
        ax.set_ylabel("Time (ns)")
        ax.set_title(_subplot_title(ds_fit, qp_name))
        ax.legend(fontsize="small", loc="upper right")
    grid.fig.tight_layout()
    return grid.fig


def plot_joint_states(ds: xr.Dataset, qubit_pairs, *, use_state_discrimination: bool = True) -> Dict[str, Figure]:
    """Both-qubit visualization vs (coupler bias, time): one figure per qubit pair.

    With state discrimination the dataset carries the joint two-qubit populations
    P00/P01/P10/P11 (vars ``state_gg/state_ge/state_eg/state_ee``, first digit = control,
    second = target); each pair gets a figure with four heatmap panels. Without state
    discrimination both qubits' ``I`` quadratures are shown instead (control | target).

    Panels are resolved from the variables present, so it works for both live and loaded
    data; ``use_state_discrimination`` is accepted for interface symmetry.

    Returns ``{pair_name: Figure}``.
    """
    pair_names = [str(p) for p in ds.qubit_pair.values]

    if "state_gg" in ds.data_vars:
        panels = _JOINT_PANELS
        title_for = lambda label: f"Control={label[0]}, Target={label[1]}"
    else:
        panels = [("I_control", "control"), ("I_target", "target")]
        title_for = lambda label: f"{label} qubit (I)"

    figures: Dict[str, Figure] = {}
    for pair in pair_names:
        fig, axs = plt.subplots(nrows=1, ncols=len(panels), figsize=(5 * len(panels), 4), squeeze=False)
        for col, (var, label) in enumerate(panels):
            ax = axs[0, col]
            ds[var].sel(qubit_pair=pair).squeeze().plot(x="amp", y="time", ax=ax, add_colorbar=True)
            ax.set_title(title_for(label))
            ax.set_xlabel(_XLABEL)
            ax.set_ylabel("Time (ns)")
        fig.tight_layout()
        figures[pair] = fig

    return figures
