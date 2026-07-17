"""QM backend factory for the scqo CLI (entry-point group ``scqo.backends``, name ``qm``).

The factory receives the device's SELECTED named setup record from its cooldown
registry (``[<cycle>.setup.<name>]`` — backend + note; since scqo v0.9 the vendor
folder is DERIVED from the keys and injected by ``load_cooldowns``):
``setup["instrument_config"]`` is the folder holding the QUAM files under
canonical names — ``state.json`` + ``wiring.json``. That folder is the single
QUAM-state authority for this device's setup (quam's own resolution via ~/.qualibrate
or QUAM_STATE_PATH is deliberately bypassed). Vendor imports stay INSIDE the function
so loading this module is cheap and vendor-free. (The virtual-twin ``qm_sim`` mode
was retired with v0.5.0.)
"""

from __future__ import annotations

from pathlib import Path

from scqo import LabConfig
from scqo.backend import Backend


def build_backend(cfg: LabConfig, setup: dict) -> Backend:
    if setup.get("backend") != "qm":
        raise SystemExit(f"the qm driver serves backend 'qm', got {setup.get('backend')!r}")
    # State-authority rule checked BEFORE loading QUAM: fail before any state file
    # is touched. Forbidden while qualibrate nodes still write QUAM directly (see
    # LCHQMDriver CLAUDE.md); the migration finish line is flipping this to "push".
    if cfg.state_sync != "pull":
        raise SystemExit(
            'lab config sets state_sync != "pull" for the QM backend: forbidden while '
            "qualibrate nodes still write QUAM directly (see LCHQMDriver CLAUDE.md)"
        )
    folder = Path(setup["instrument_config"])
    missing = [n for n in ("state.json", "wiring.json") if not (folder / n).is_file()]
    if missing:
        raise SystemExit(
            f"qm setup: {', '.join(missing)} not found in {folder} — "
            "canonical QUAM filenames required"
        )
    from customized.scqo.backend import QMBackend

    return QMBackend.load(state_path=str(folder))
