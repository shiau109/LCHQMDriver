"""Population helpers shared by the swap-based-reset visualization nodes
(`LCH_qc_swap_paramreset`, `LCH_qc_unidirectional_coupling`).

Both nodes read out a set of qubits at the end of each shot and sweep a `round` axis.
With state discrimination the probe now saves the **per-shot** discriminated states
(`ds_raw["state"]`, dims `(qubit, shot, round)`); these helpers turn that into either:

- the **joint** multi-qubit populations P(000), P(001), ... P(111) -- the correlated
  outcome of all measured qubits in the same shot (requires per-shot data); or
- the **per-qubit marginal** populations P(excited) (also works on historical data
  saved under the old `(qubit, round)` schema, which has no `shot` axis).

The joint computation generalizes the two-qubit precedent in
`customized.probes.pair_qq_chevron` (P00/P01/P10/P11) to N qubits, but in Python.

Bitstring convention: the **first measured qubit is the leftmost / most-significant
digit** (the `qubit` coordinate order is the order the probe reads them out).
"""

import itertools
from typing import Dict, List

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr


def _qubit_names(state: xr.DataArray) -> List[str]:
    return [str(q) for q in state.qubit.values]


def joint_state_populations(state: xr.DataArray) -> xr.DataArray:
    """Joint multi-qubit populations from per-shot discriminated states.

    `state` must have dims including `qubit`, `shot` and `round` (the per-shot schema).
    Returns a DataArray with dims `(joint_state, round)` whose `joint_state` coordinate is
    the bitstring label per measured qubit (first measured qubit = leftmost digit). At each
    round the populations sum to 1.
    """
    names = _qubit_names(state)
    n = len(names)
    # (round, shot, qubit), binarized to {0, 1} (>=1 -> excited).
    s = (state.transpose("round", "shot", "qubit").values >= 1).astype(np.int64)
    nrounds, nshots, _ = s.shape

    # Per-shot integer code with the first qubit as the most-significant bit.
    weights = (2 ** np.arange(n)[::-1]).astype(np.int64)
    codes = (s * weights).sum(axis=2)  # (round, shot)

    labels = ["".join(bits) for bits in itertools.product("01", repeat=n)]
    pops = np.zeros((2 ** n, nrounds))
    for r in range(nrounds):
        pops[:, r] = np.bincount(codes[r], minlength=2 ** n) / nshots

    # NB: use state["round"], not state.round (the latter is DataArray.round, a method).
    return xr.DataArray(
        pops,
        dims=["joint_state", "round"],
        coords={"joint_state": labels, "round": state["round"].values},
    )


def marginal_populations(state: xr.DataArray) -> xr.DataArray:
    """Per-qubit excited-state population vs round, dims `(qubit, round)`.

    Works on the per-shot schema (averages over `shot`) and is a no-op passthrough on the
    old shot-averaged schema (no `shot` dim), where `state` already is the population.
    """
    if "shot" in state.dims:
        return (state >= 1).mean("shot")
    return state


def plot_populations(
    ds_raw: xr.Dataset,
    *,
    multiplexed: bool,
    use_state_discrimination: bool,
    title: str,
    xlabel: str,
) -> Dict[str, plt.Figure]:
    """Build a single combined population-vs-round figure; return ``{key: Figure}``.

    - state discrimination + ``multiplexed`` + per-shot data -> joint populations
      (one line per bitstring ``000``..); key ``"joint_populations"``.
    - state discrimination otherwise -> per-qubit marginal P(excited), one line per
      measured qubit; key ``"populations"``.
    - no state discrimination -> raw ``I`` quadrature, one line per qubit; key ``"raw_I"``.
    """
    fig, ax = plt.subplots(figsize=(7, 4.5))

    if use_state_discrimination and "state" in ds_raw:
        state = ds_raw["state"]
        if multiplexed and "shot" in state.dims:
            pops = joint_state_populations(state)
            for label in [str(v) for v in pops.joint_state.values]:
                pops.sel(joint_state=label).plot(x="round", ax=ax, marker="o", label=f"|{label}⟩")
            ax.set_ylabel("Population")
            ax.legend(title="state", ncol=2, fontsize="small")
            key = "joint_populations"
        else:
            marg = marginal_populations(state)
            for q in _qubit_names(state):
                marg.sel(qubit=q).plot(x="round", ax=ax, marker="o", label=q)
            ax.set_ylabel("P(excited)")
            ax.legend(title="qubit")
            key = "populations"
    else:
        for q in [str(v) for v in ds_raw.qubit.values]:
            ds_raw["I"].sel(qubit=q).plot(x="round", ax=ax, marker="o", label=q)
        ax.set_ylabel("I [V]")
        ax.legend(title="qubit")
        key = "raw_I"

    ax.set_xlabel(xlabel)
    ax.set_title(title)
    fig.tight_layout()
    return {key: fig}
