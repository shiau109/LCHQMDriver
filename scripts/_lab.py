"""Shared helper for the QM student scripts: build a Session from the lab config.

Mirror of LCHQBDriver/scripts/_lab.py. With ``backend = "qm"`` the QUAM machine is
loaded via ``QMBackend.load()`` (quam_state/); ``backend = "simulated"`` (or no
config) runs offline on demo qubits. Per the state-authority rule, QM sessions are
forced to ``state_sync = "pull"`` until qualibrate-node migration completes (see
LCHQMDriver CLAUDE.md).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Make `import customized` work when the repo is not pip-installed: running a script
# here puts scripts/ on sys.path, not the repo root.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scqo import LabConfig, Session, load_lab_config, make_session
from scqo.testing import InMemoryDevice, SimulatedBackend

import customized.scqo.experiments  # noqa: F401  registers the QM experiments

DEMO_QUBITS = {
    "q1": {"readout_freq": 5.95e9, "drive_freq": 3.87e9, "pi_amp": 0.20},
    "q2": {"readout_freq": 6.05e9, "drive_freq": 4.01e9, "pi_amp": 0.18},
}


def default_qubits(sess: Session) -> list[str]:
    """Measurable qubits for 'run on everything' defaults (mirror of LCHQBDriver:
    the lab convention is qubits q*; couplers/auxiliary elements are excluded)."""
    return [q for q in sess.device_state() if q.startswith("q")]


def build_session(config_path: str | None = None) -> tuple[Session, LabConfig]:
    cfg = load_lab_config(config_path)
    if cfg.backend == "qm":
        from customized.scqo.backend import QMBackend

        backend = QMBackend.load()
        if cfg.state_sync != "pull":
            raise SystemExit(
                'lab config sets state_sync != "pull" for the QM backend: forbidden while '
                "qualibrate nodes still write QUAM directly (see LCHQMDriver CLAUDE.md)"
            )
    elif cfg.backend == "qm_sim":
        # Virtual twin: load a REAL QUAM state (working copy), acquire simulated data.
        # Writebacks are saved to that working copy ONLY — never the live quam_state/.
        from pathlib import Path

        from customized.scqo.backend import QMDeviceModel
        from quam_config import Quam

        state_dir = cfg.extras.get("qm", {}).get("state_dir")
        if not state_dir or not (Path(state_dir) / "state.json").is_file():
            raise SystemExit(
                'backend "qm_sim" needs [qm] state_dir = "<folder>" in the lab config, '
                "holding a WORKING COPY of state.json + wiring.json (not the live quam_state/)"
            )
        machine = Quam.load(str(state_dir))
        backend = SimulatedBackend(QMDeviceModel(machine, state_dir=str(state_dir)))
    elif cfg.backend == "simulated":
        backend = SimulatedBackend(InMemoryDevice(DEMO_QUBITS))
    else:
        raise SystemExit(
            f"unsupported backend {cfg.backend!r} in {cfg.source or 'defaults'} "
            "(this repo drives 'qm', 'qm_sim' or 'simulated'; 'qblox' scripts live in LCHQBDriver)"
        )
    return make_session(backend, cfg), cfg
