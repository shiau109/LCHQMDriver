"""Fixed-time qubit-flux x coupler-flux estimate adapter.

This is intentionally an **empty estimator** (mirrors `LCH_pair_qq_chevron.analysis`): it
performs no fitting and extracts no quantities for state writeback. Its only purpose is
to satisfy the node's analyse/outcome flow while the visualization is produced by
`plotting.plot_fixed_time_2d`. A real fit can be dropped in here later without touching
the probe or the shell.
"""

from typing import Dict

import xarray as xr


def estimate(ds_raw: xr.Dataset, *, use_state_discrimination: bool) -> Dict:
    """No-op estimator: return a per-pair placeholder marking acquisition as successful.

    `use_state_discrimination` is accepted for interface symmetry with the real
    estimators (and a future fit), but is unused here.
    """
    return {str(qp): {"success": True} for qp in ds_raw.qubit_pair.values}
