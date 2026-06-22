"""Fixed-time qubit-flux x coupler-flux 2D visualization: one figure per qubit pair.

Mirrors `LCH_pair_qq_chevron.plotting.plot_chevron_2d`. With state discrimination the probe
saves the joint two-qubit populations P00/P01/P10/P11 (vars
`state_gg/state_ge/state_eg/state_ee`, first digit = control, second = target); each
pair gets a figure with four color-map panels (00, 01, 10, 11) over the coupler flux
amplitude (x) x qubit flux amplitude (y) sweep. Without state discrimination the raw I
quadratures are shown instead (control | target).
"""

from typing import Dict

import matplotlib.pyplot as plt
import xarray as xr

# Joint-population variable -> display label (first digit = control, second = target).
_JOINT_PANELS = [
    ("state_gg", "00"),
    ("state_ge", "01"),
    ("state_eg", "10"),
    ("state_ee", "11"),
]


def plot_fixed_time_2d(ds_raw: xr.Dataset, qubit_pairs, *, use_state_discrimination: bool) -> Dict[str, plt.Figure]:
    """Build one 2D color-map figure per qubit pair; return {pair_name: Figure}.

    Joint-population panels are drawn when the dataset carries them (resolved from the
    variables, so it works for both live and loaded data); otherwise the raw I/Q
    control/target panels are drawn. `use_state_discrimination` is accepted for
    interface symmetry.
    """
    pair_names = [str(p) for p in ds_raw.qubit_pair.values]

    if "state_gg" in ds_raw:
        panels = _JOINT_PANELS
        title_for = lambda label: f"Control={label[0]}, Target={label[1]}"
    else:
        panels = [("I_control", "control"), ("I_target", "target")]
        title_for = lambda label: label

    figures: Dict[str, plt.Figure] = {}
    for pair in pair_names:
        fig, axs = plt.subplots(nrows=1, ncols=len(panels), figsize=(5 * len(panels), 4), squeeze=False)
        for col, (var, label) in enumerate(panels):
            ax = axs[0, col]
            ds_raw[var].sel(qubit_pair=pair).plot(
                x="coupler_amplitude", y="qubit_amplitude", ax=ax, add_colorbar=True
            )
            ax.set_title(title_for(label))
            ax.set_xlabel("Coupler flux amplitude")
            ax.set_ylabel("Qubit flux amplitude")
        fig.suptitle(f"Fixed-time qubit-flux x coupler-flux sweep - {pair}")
        fig.tight_layout()
        figures[pair] = fig

    return figures
