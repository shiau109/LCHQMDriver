"""Unit tests for the shared swap-reset population helpers
(`customized.node._qc_populations`). Pure Python, no QM / hardware.

Mirrors the per-shot discriminated-state schema the probes now save:
`state` with dims `(qubit, shot, round)`.
"""

import matplotlib

matplotlib.use("Agg", force=True)  # headless: no display needed for the figure assertions

import numpy as np
import pytest
import xarray as xr

from customized.node._qc_populations import (
    joint_state_populations,
    marginal_populations,
    plot_population_maps,
    plot_populations,
)


def _make_state() -> xr.DataArray:
    """3 qubits, 4 shots, 2 rounds.

    round 0: half the shots are |100>, half are |011>.
    round 1: every shot is |111>.
    (q2 and q3 are identical here by construction.)
    """
    # per-qubit (shot, round) arrays
    q1 = np.array([[1, 1], [1, 1], [0, 1], [0, 1]])
    q2 = np.array([[0, 1], [0, 1], [1, 1], [1, 1]])
    q3 = q2.copy()
    data = np.stack([q1, q2, q3], axis=0)  # (qubit, shot, round)
    return xr.DataArray(
        data,
        dims=["qubit", "shot", "round"],
        coords={"qubit": ["q1", "q2", "q3"], "shot": np.arange(4), "round": np.arange(2)},
    )


def test_joint_labels_order_and_first_qubit_is_msb():
    pops = joint_state_populations(_make_state())
    assert list(pops.joint_state.values) == [
        "000", "001", "010", "011", "100", "101", "110", "111",
    ]
    assert pops.dims == ("joint_state", "round")


def test_joint_populations_sum_to_one_per_round():
    pops = joint_state_populations(_make_state())
    np.testing.assert_allclose(pops.sum("joint_state").values, 1.0)


def test_joint_populations_match_constructed_distribution():
    pops = joint_state_populations(_make_state())
    # round 0: |100> (q1 MSB) and |011> at 0.5 each, nothing else.
    assert pops.sel(joint_state="100", round=0) == pytest.approx(0.5)
    assert pops.sel(joint_state="011", round=0) == pytest.approx(0.5)
    others0 = [s for s in pops.joint_state.values if s not in ("100", "011")]
    np.testing.assert_allclose(pops.sel(joint_state=others0, round=0).values, 0.0)
    # round 1: |111> only.
    assert pops.sel(joint_state="111", round=1) == pytest.approx(1.0)


def test_marginals_match_per_qubit_mean():
    marg = marginal_populations(_make_state())
    assert marg.dims == ("qubit", "round")
    np.testing.assert_allclose(marg.sel(qubit="q1").values, [0.5, 1.0])
    np.testing.assert_allclose(marg.sel(qubit="q2").values, [0.5, 1.0])
    np.testing.assert_allclose(marg.sel(qubit="q3").values, [0.5, 1.0])


def test_marginals_passthrough_on_historical_schema():
    # old shot-averaged schema (no `shot` dim) -> returned unchanged.
    avg = xr.DataArray(
        [[0.5, 1.0], [0.5, 1.0]],
        dims=["qubit", "round"],
        coords={"qubit": ["q1", "q2"], "round": np.arange(2)},
    )
    out = marginal_populations(avg)
    xr.testing.assert_identical(out, avg)


def test_plot_joint_returns_figure_with_all_states():
    ds = xr.Dataset({"state": _make_state()})
    figs = plot_populations(
        ds, multiplexed=True, use_state_discrimination=True,
        title="t", xlabel="x",
    )
    assert set(figs) == {"joint_populations"}
    ax = figs["joint_populations"].axes[0]
    assert len(ax.get_lines()) == 8  # all 2^3 states plotted


def test_plot_marginal_when_not_multiplexed():
    ds = xr.Dataset({"state": _make_state()})
    figs = plot_populations(
        ds, multiplexed=False, use_state_discrimination=True,
        title="t", xlabel="x",
    )
    assert set(figs) == {"populations"}
    assert len(figs["populations"].axes[0].get_lines()) == 3  # one per qubit


def test_plot_raw_when_no_state_discrimination():
    raw_i = xr.DataArray(
        np.zeros((3, 2)),
        dims=["qubit", "round"],
        coords={"qubit": ["q1", "q2", "q3"], "round": np.arange(2)},
    )
    ds = xr.Dataset({"I": raw_i})
    figs = plot_populations(
        ds, multiplexed=True, use_state_discrimination=False,
        title="t", xlabel="x",
    )
    assert set(figs) == {"raw_I"}
    assert len(figs["raw_I"].axes[0].get_lines()) == 3


# --- 2D (round x amplitude) schema: `LCH_qc_N_swap_amp` ----------------------------------


def _make_state_amp() -> xr.DataArray:
    """2 qubits, 4 shots, 3 amplitudes, 2 rounds -- the 2D per-shot schema the amp probe saves.

    The two-qubit slice of `_make_state()` is broadcast across a `qubit_amplitude` axis, so
    every amplitude carries the same known distribution (round 0: half |10>, half |01>; round
    1: all |11>).
    """
    base = _make_state().isel(qubit=slice(0, 2))  # (qubit=2, shot=4, round=2)
    amps = np.linspace(0.10, 0.12, 3)
    return (
        base.expand_dims(qubit_amplitude=len(amps))
        .assign_coords(qubit_amplitude=amps)
        .transpose("qubit", "shot", "qubit_amplitude", "round")
    )


def _n_map_panels(fig) -> int:
    # Each 2D-map panel carries a per-axes title (state label / qubit name); the shared
    # colorbar and any hidden padding axes do not -- so titled axes == number of maps.
    return sum(bool(ax.get_title()) for ax in fig.axes)


def test_joint_populations_2d_preserves_amplitude_axis():
    pops = joint_state_populations(_make_state_amp())
    assert pops.dims == ("joint_state", "qubit_amplitude", "round")
    assert pops.sizes["joint_state"] == 4  # 2 measured qubits
    np.testing.assert_allclose(pops.sum("joint_state").values, 1.0)


def test_joint_populations_2d_slice_matches_1d():
    state_amp = _make_state_amp()
    pops2d = joint_state_populations(state_amp)
    pops1d = joint_state_populations(state_amp.isel(qubit_amplitude=0))
    np.testing.assert_allclose(
        pops2d.isel(qubit_amplitude=0).transpose("joint_state", "round").values,
        pops1d.transpose("joint_state", "round").values,
    )


def test_plot_population_maps_joint_one_per_state():
    ds = xr.Dataset({"state": _make_state_amp()})
    figs = plot_population_maps(
        ds, multiplexed=True, use_state_discrimination=True,
        title="t", xlabel="x", ylabel="y", y_dim="qubit_amplitude",
    )
    assert set(figs) == {"joint_state_maps"}
    assert _n_map_panels(figs["joint_state_maps"]) == 4  # all 2^2 states


def test_plot_population_maps_marginal_one_per_qubit():
    ds = xr.Dataset({"state": _make_state_amp()})
    figs = plot_population_maps(
        ds, multiplexed=False, use_state_discrimination=True,
        title="t", xlabel="x", ylabel="y", y_dim="qubit_amplitude",
    )
    assert set(figs) == {"population_maps"}
    assert _n_map_panels(figs["population_maps"]) == 2  # one per qubit


def test_plot_population_maps_raw_when_no_state_discrimination():
    raw_i = xr.DataArray(
        np.zeros((2, 3, 2)),
        dims=["qubit", "qubit_amplitude", "round"],
        coords={"qubit": ["q1", "q2"], "qubit_amplitude": np.linspace(0.10, 0.12, 3), "round": np.arange(2)},
    )
    ds = xr.Dataset({"I": raw_i})
    figs = plot_population_maps(
        ds, multiplexed=True, use_state_discrimination=False,
        title="t", xlabel="x", ylabel="y", y_dim="qubit_amplitude",
    )
    assert set(figs) == {"raw_I_maps"}
    assert _n_map_panels(figs["raw_I_maps"]) == 2
