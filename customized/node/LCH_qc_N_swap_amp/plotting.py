"""N-swap x qubit-flux-amplitude visualization: one figure per measured qubit.

Three panels sharing the amplitude (y) axis:
  1. the raw 2D map -- population (or raw I) vs the number of swaps N (x) and the swept
     ctrl flux amplitude (y);
  2. the per-row fitted swap-oscillation frequency `f` (cycles per swap, x) vs amplitude;
  3. the per-row fitted contrast `a` vs amplitude -- the resonance indicator that picks
     `best_amplitude` (a detuned swap oscillates faster but shallower).
Successful rows are filled markers, rejected rows hollow; `best_amplitude` is a dashed
line across all panels.
"""

from typing import Dict

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


def plot_amp_rounds_2d(sq_data: xr.Dataset, fit: Dict, *, qubit_name: str, use_state_discrimination: bool) -> plt.Figure:
    """Build the 2D-map + f/contrast-vs-amplitude figure for one measured qubit.

    `sq_data` is the per-qubit dataset (variable `signal` over
    `qubit_amplitude x round`, population when `use_state_discrimination` else raw I);
    `fit` is that qubit's entry from `analysis.fit` (per-row `amplitudes` / `f` / `a` /
    `row_success` lists + `best_amplitude`).
    """
    amplitudes = np.asarray(fit["amplitudes"], dtype=float)
    f = np.asarray(fit["f"], dtype=float)
    a = np.asarray(fit["a"], dtype=float)
    row_success = np.asarray(fit["row_success"], dtype=bool)
    best_amplitude = fit["best_amplitude"]

    fig, (ax_map, ax_f, ax_a) = plt.subplots(
        nrows=1, ncols=3, figsize=(12.5, 4.2), sharey=True, gridspec_kw={"width_ratios": [3, 2, 2]}
    )

    qm = sq_data["signal"].plot(x="round", y="qubit_amplitude", ax=ax_map, add_colorbar=False)
    fig.colorbar(qm, ax=ax_map, fraction=0.046, pad=0.05, label="population" if use_state_discrimination else "I [V]")
    ax_map.set_xlabel("number of swaps N")
    ax_map.set_ylabel("ctrl flux amplitude [V]")
    ax_map.set_title("signal vs N x amplitude")

    for ax, values, xlabel, title in (
        (ax_f, f, "f [cycles/swap]", "swap frequency"),
        (ax_a, a, "contrast a", "oscillation contrast"),
    ):
        if row_success.any():
            ax.plot(values[row_success], amplitudes[row_success], "o", color="C0", label="fit ok")
        if (~row_success).any():
            ax.plot(values[~row_success], amplitudes[~row_success], "o", mfc="none", color="0.6", label="fit rejected")
        ax.set_xlabel(xlabel)
        ax.set_title(title)

    if best_amplitude is not None:
        for ax in (ax_map, ax_f, ax_a):
            ax.axhline(best_amplitude, color="C3", ls="--", lw=1)
        ax_a.plot([], [], color="C3", ls="--", lw=1, label=f"best amp = {best_amplitude:.4g} V (max contrast)")
    ax_a.legend(loc="best", fontsize=8)

    fig.suptitle(f"N-swap vs ctrl flux amplitude - {qubit_name}")
    fig.tight_layout()
    return fig
