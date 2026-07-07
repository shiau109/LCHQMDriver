"""QM backend factory for the scqo CLI (entry-point group ``scqo.backends``, name ``qm``).

Serves both modes of the family: ``qm`` (real OPX1000) and ``qm_sim`` (the virtual
twin: a WORKING COPY of your real QUAM state, synthetic data). Vendor imports stay
INSIDE the branches so loading this module is cheap and vendor-free.
"""

from __future__ import annotations

from scqo import LabConfig
from scqo.backend import Backend


def build_backend(cfg: LabConfig) -> Backend:
    if cfg.backend == "qm":
        # State-authority rule checked BEFORE loading QUAM (improvement over the old
        # scripts/_lab.py, which loaded first): fail before any state file is touched.
        if cfg.state_sync != "pull":
            raise SystemExit(
                'lab config sets state_sync != "pull" for the QM backend: forbidden while '
                "qualibrate nodes still write QUAM directly (see LCHQMDriver CLAUDE.md)"
            )
        from customized.scqo.backend import QMBackend

        # Honor [qm] state_dir like the qm_sim branch below does. Without this the
        # QUAM state comes from quam's default resolution (~/.qualibrate config or
        # QUAM_STATE_PATH), which on the lab server silently pointed at a stale
        # dev-era state — the scqo lab config must stay the single authority.
        return QMBackend.load(state_path=cfg.extras.get("qm", {}).get("state_dir"))
    if cfg.backend == "qm_sim":
        # Virtual twin: load a REAL QUAM state (working copy), acquire simulated data.
        # Writebacks are saved to that working copy ONLY — never the live quam_state/.
        from pathlib import Path

        from customized.scqo.backend import QMDeviceModel
        from quam_config import Quam
        from scqo.testing import SimulatedBackend

        state_dir = cfg.extras.get("qm", {}).get("state_dir")
        if not state_dir or not (Path(state_dir) / "state.json").is_file():
            raise SystemExit(
                'backend "qm_sim" needs [qm] state_dir = "<folder>" in the lab config, '
                "holding a WORKING COPY of state.json + wiring.json (not the live quam_state/)"
            )
        machine = Quam.load(str(state_dir))
        return SimulatedBackend(QMDeviceModel(machine, state_dir=str(state_dir)))
    raise SystemExit(f"the qm driver builds 'qm' or 'qm_sim', got {cfg.backend!r}")
