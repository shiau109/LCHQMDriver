"""Fixed-time qubit-flux x coupler-flux 2D visualization: one figure per qubit pair.

Mirrors `LCH_pair_qq_chevron.plotting.plot_chevron_2d`. With state discrimination the probe
saves the joint two-qubit populations P00/P01/P10/P11 (vars
`state_gg/state_ge/state_eg/state_ee`, first digit = control, second = target); each
pair gets a figure with four color-map panels (00, 01, 10, 11) over the coupler flux
amplitude (x) x qubit flux amplitude (y) sweep. Without state discrimination the raw I
quadratures are shown instead (control | target).

Each figure is stamped with how it was acquired (swap path + amp mode), and in DIRECT mode
both flux axes carry a secondary scale so absolute volts AND the unitless prefactor (a/ref)
are readable at once. In MACRO mode the coupler is inert (not swept), so the x-axis is
flagged and the dual-unit secondary scale is omitted.
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


def _flux_qubit(qp, flux_role: str):
    """Return the qubit of the pair whose z line carries the qubit flux pulse."""
    return qp.qubit_target if flux_role == "target" else qp.qubit_control


def _op_amplitude(channel, op_name):
    """Return |amplitude| of a named operation on a channel, or None if unavailable."""
    try:
        amp = abs(float(channel.operations[op_name].amplitude))
        return amp if amp > 0 else None
    except Exception:
        return None


def _add_alt_axes(ax, amp_mode: str, qubit_ref, coupler_ref):
    """Add a secondary scale to each flux axis so both units are readable.

    Primary axis = the swept unit (`amp_mode`). The secondary axis converts via the per-axis
    reference amplitude: absolute mode adds a `prefactor = a/ref` scale; prefactor mode adds
    an `amplitude [V] = prefactor * ref` scale. Each axis uses its own ref (coupler on x,
    qubit on y).
    """
    if amp_mode == "absolute":
        sec_label = "prefactor (a/ref)"
        make = lambda r: ((lambda v: v / r), (lambda p: p * r))
    else:
        sec_label = "amplitude [V]"
        make = lambda r: ((lambda p: p * r), (lambda v: v / r))

    if coupler_ref:
        fwd, inv = make(coupler_ref)
        sx = ax.secondary_xaxis("top", functions=(fwd, inv))
        sx.set_xlabel(sec_label)
    if qubit_ref:
        fwd, inv = make(qubit_ref)
        sy = ax.secondary_yaxis("right", functions=(fwd, inv))
        sy.set_ylabel(sec_label)


def plot_fixed_time_2d(
    ds_raw: xr.Dataset,
    qubit_pairs,
    *,
    use_state_discrimination: bool,
    swap_via_macro: bool = False,
    amp_mode: str = "absolute",
    qubit_operation: str = "const",
    coupler_operation: str = "const",
    flux_role: str = "control",
    swap_operation: str = "iswap",
) -> Dict[str, plt.Figure]:
    """Build one 2D color-map figure per qubit pair; return {pair_name: Figure}.

    Joint-population panels are drawn when the dataset carries them (resolved from the
    variables, so it works for both live and loaded data); otherwise the raw I/Q
    control/target panels are drawn. `use_state_discrimination` is accepted for
    interface symmetry.

    `swap_via_macro` / `amp_mode` are stamped on the figure so each saved plot records how
    it was acquired. In DIRECT mode both flux axes get a secondary scale (absolute volts +
    prefactor), resolved from the swept ops' reference amplitudes (`qubit_operation` on the
    `flux_role` qubit's z, `coupler_operation` on the coupler). In MACRO mode the coupler is
    pinned (x-axis inert) and the secondary scale is omitted. `swap_operation` is accepted
    for interface symmetry.
    """
    pair_names = [str(p) for p in ds_raw.qubit_pair.values]
    try:
        pair_by_name = {p.name: p for p in qubit_pairs}
    except TypeError:
        pair_by_name = {}

    if "state_gg" in ds_raw:
        panels = _JOINT_PANELS
        title_for = lambda label: f"Control={label[0]}, Target={label[1]}"
    else:
        panels = [("I_control", "control"), ("I_target", "target")]
        title_for = lambda label: label

    swap_label = "macro .apply()" if swap_via_macro else "direct play"
    amp_label = "absolute (V)" if amp_mode == "absolute" else "prefactor"
    amp_unit = "V" if amp_mode == "absolute" else "prefactor"
    cplr_xlabel = (
        "Coupler flux amplitude (not swept - macro pins coupler at decouple)"
        if swap_via_macro
        else f"Coupler flux amplitude [{amp_unit}]"
    )

    figures: Dict[str, plt.Figure] = {}
    for pair in pair_names:
        qp = pair_by_name.get(pair)

        # Reference amplitudes for the dual-unit secondary axes (direct mode only).
        qubit_ref = coupler_ref = None
        if qp is not None and not swap_via_macro:
            qubit_ref = _op_amplitude(_flux_qubit(qp, flux_role).z, qubit_operation)
            coupler_ref = _op_amplitude(qp.coupler, coupler_operation) if qp.coupler is not None else None

        wide = bool(qubit_ref) and not swap_via_macro  # leave room for the right secondary axis
        fig, axs = plt.subplots(
            nrows=1, ncols=len(panels), figsize=((6.0 if wide else 5.0) * len(panels), 4.2), squeeze=False
        )
        for col, (var, label) in enumerate(panels):
            ax = axs[0, col]
            qm = ds_raw[var].sel(qubit_pair=pair).plot(
                x="coupler_amplitude", y="qubit_amplitude", ax=ax, add_colorbar=False
            )
            ax.set_title(title_for(label))
            ax.set_xlabel(cplr_xlabel)
            ax.set_ylabel(f"Qubit flux amplitude [{amp_unit}]")
            if not swap_via_macro:
                _add_alt_axes(ax, amp_mode, qubit_ref, coupler_ref)
            # Manual colorbar with extra pad so it clears the right secondary axis.
            fig.colorbar(qm, ax=ax, fraction=0.046, pad=0.22 if wide else 0.05)

        suptitle = (
            f"Fixed-time qubit-flux x coupler-flux sweep - {pair}\n"
            f"swap: {swap_label}  |  amp: {amp_label}"
        )
        fig.suptitle(suptitle)
        fig.tight_layout()
        figures[pair] = fig

    return figures
