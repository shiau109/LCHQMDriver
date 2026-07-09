"""N-swap x qubit-flux-amplitude estimate adapter.

This is intentionally an **empty estimator**: it performs no fitting and extracts no
quantities for state writeback. Its only purpose is to satisfy the node's analyse/outcome
flow while the visualization (one 2D population map per joint state, population vs the
number of swaps N and the swept ctrl flux amplitude) is produced by
`plotting.plot_amp_state_maps`. A real fit (e.g. a per-amplitude swap-oscillation cosine)
can be dropped in here later without touching the probe or the shell.
"""

from typing import Dict

import xarray as xr


def estimate(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Dict:
    """No-op estimator: return a per-qubit placeholder marking acquisition as successful.

    `use_state_discrimination` is accepted for interface symmetry with the real
    estimators (and a future fit), but is unused here.
    """
    return {str(q): {"success": True} for q in ds_raw.qubit.values}
