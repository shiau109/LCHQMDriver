"""Self-contained qubit-pair subplot grid for this node's plotting.

The vendored plotting modules import ``QubitPairGrid``/``grid_pair_names`` from
``calibration_utils.pair_grid``, but that module is currently absent from the repo (it is not
listed in any sync manifest), so importing it raises ``ModuleNotFoundError``. To keep this custom
node working regardless of the vendored state, we provide an API-compatible, dependency-free
implementation here.

``QubitPairGrid(grid_names, pair_names, size)`` builds a (roughly square) grid of subplots — one per
qubit pair — and exposes ``.fig`` / ``.axes`` / ``.name_dicts`` so it iterates with
:func:`qualibration_libs.plotting.grid_iter`, yielding ``(ax, {"qubit": pair_name})`` for each pair.
"""

import math

import matplotlib.pyplot as plt

__all__ = ["QubitPairGrid", "grid_pair_names"]


def grid_pair_names(qubit_pairs):
    """Return ``(grid_location_strings, pair_names)`` for the given qubit pairs.

    Mirrors ``qualibration_libs.plotting.grids.grid_pair_names``: the location string is the
    control/target grid locations joined by ``-`` (kept for API parity; the layout below is
    index-based and does not parse it).
    """
    return (
        [f"{qp.qubit_control.grid_location}-{qp.qubit_target.grid_location}" for qp in qubit_pairs],
        [qp.name for qp in qubit_pairs],
    )


class QubitPairGrid:
    """Roughly-square grid of subplots, one per qubit pair.

    Parameters
    ----------
    grid_names : list[str]
        Per-pair location strings (accepted for API parity; not used for placement here).
    pair_names : list[str]
        Qubit-pair names; each becomes ``{"qubit": name}`` in :attr:`name_dicts`.
    size : int
        Per-subplot size in inches.
    """

    def __init__(self, grid_names, pair_names, size: int = 4):
        n = max(len(pair_names), 1)
        ncols = int(math.ceil(math.sqrt(n)))
        nrows = int(math.ceil(n / ncols))

        figure, all_axes = plt.subplots(nrows, ncols, figsize=(ncols * size, nrows * size), squeeze=False)
        flat_axes = [ax for row in all_axes for ax in row]

        used_axes = flat_axes[: len(pair_names)]
        for ax in flat_axes[len(pair_names):]:
            ax.axis("off")

        self.fig = figure
        self.all_axes = all_axes
        self.axes = [used_axes]
        self.name_dicts = [[{"qubit": name} for name in pair_names]]
