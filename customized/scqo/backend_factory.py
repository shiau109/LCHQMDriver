"""QM backend factory for the scqo CLI (entry-point group ``scqo.backends``, name ``qm``).

The factory receives the device's SELECTED named setup record from its cooldown
registry (``[<cycle>.setup.<name>]`` — backend + note; since scqo v0.9 the vendor
folder is DERIVED from the keys and injected by ``load_cooldowns``):
``setup["instrument_config"]`` is the folder holding the QUAM files under
canonical names — ``state.json`` + ``wiring.json``. That folder is the single
QUAM-state authority for this device's setup (quam's own resolution via ~/.qualibrate
or QUAM_STATE_PATH is deliberately bypassed). It also receives the device's ROSTER,
the authority on which entities exist: the driver serves views BY ENTITY NAME
(``q1_xy`` -> its drive view over QUAM's ``q1.xy``, ``q1_q2_c_z`` -> the pair's
TunableCoupler), so the roster is threaded into the backend and every name resolves
through it. Vendor imports stay INSIDE the function so loading this module is cheap
and vendor-free. (The virtual-twin ``qm_sim`` mode was retired with v0.5.0.)
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from scqo import LabConfig
from scqo.backend import Backend

if TYPE_CHECKING:
    from scqo.roster import Roster


def build_backend(cfg: LabConfig, setup: dict, roster: "Roster") -> Backend:
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
    from customized.quam_fields import flux_point_problems
    from customized.scqo.backend import QMBackend

    backend = QMBackend.load(state_path=str(folder), roster=roster)

    # The governed knob must BE the applied bias. Checked once, here, rather than
    # inside get/set_idle_flux: that getter runs during pull-seeding, so refusing
    # there would abort session construction with no context, and the accessor is
    # shared with the qualibrate path where a different point is legitimate.
    problems = flux_point_problems(backend.machine)
    if problems:
        raise SystemExit(
            f"qm setup: flux points in {folder / 'state.json'} disagree with the "
            f"bias every probe applies, so idle_flux would be a knob the hardware "
            f"never sees:\n  - " + "\n  - ".join(problems))
    return backend
