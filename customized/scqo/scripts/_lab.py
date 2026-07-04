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
# here puts customized/scqo/scripts on sys.path, not the repo root (3 levels up).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scqo import LabConfig, Session, load_lab_config, make_session
from scqo.testing import InMemoryDevice, SimulatedBackend

import customized.scqo.experiments  # noqa: F401  registers the QM experiments

DEMO_QUBITS = {
    "q1": {"readout_freq": 5.95e9, "drive_freq": 3.87e9, "pi_amp": 0.20},
    "q2": {"readout_freq": 6.05e9, "drive_freq": 4.01e9, "pi_amp": 0.18},
}


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
    elif cfg.backend == "simulated":
        backend = SimulatedBackend(InMemoryDevice(DEMO_QUBITS))
    else:
        raise SystemExit(
            f"unsupported backend {cfg.backend!r} in {cfg.source or 'defaults'} "
            "(this repo drives 'qm' or 'simulated'; 'qblox' scripts live in LCHQBDriver)"
        )
    return make_session(backend, cfg), cfg
