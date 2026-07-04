"""Run any scqo-cataloged experiment on the QM backend — mirror of LCHQBDriver's script.

    python customized/scqo/scripts/run_experiment.py                       # list catalog
    python customized/scqo/scripts/run_experiment.py qubit_ramsey --qubits q1 --tag cooldown7

Backend, data location and device name come from ``~/.scqo/config.toml`` (see
scqo.labconfig); students edit nothing in this repo. With ``backend = "qm"`` the QUAM
machine is loaded via ``QMBackend.load()`` (quam_state/); with ``backend = "simulated"``
(or no config) everything runs offline on demo qubits.

Only the three migrated experiments run here (resonator_spectroscopy, qubit_ramsey,
qubit_power_rabi); the other calibrations still run through the qualibrate GUI.
NOTE: per the state-authority rule, QM sessions stay on ``state_sync = "pull"`` until
every qualibrate node is migrated (see CLAUDE.md).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Make `import customized` work when the repo is not pip-installed: running this
# script puts customized/scqo/scripts on sys.path, not the repo root (3 levels up).
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


def _parse_value(text: str):
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("experiment", nargs="?", help="experiment name; omit to list the catalog")
    parser.add_argument("--params", help="parameters as a JSON file path or an inline JSON string")
    parser.add_argument("--qubits", nargs="+", help="qubits to measure (default: all in the device)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override one parameter (repeatable), e.g. --set num_points=201")
    parser.add_argument("--tag", action="append", default=[], dest="tags",
                        help="searchable tag for this run (repeatable)")
    parser.add_argument("--note", default="", help="free-text note stored with the run")
    parser.add_argument("--no-update", action="store_true",
                        help="analyze only; do not write fitted values back to the device")
    parser.add_argument("--config", help="lab config path (default: $SCQO_CONFIG or ~/.scqo/config.toml)")
    args = parser.parse_args()

    sess, cfg = build_session(args.config)

    if not args.experiment:
        print(f"# lab config: {cfg.source or 'built-in defaults (simulated, nothing saved)'}")
        for entry in sess.catalog():
            print(f"{entry['name']:32s} {entry['description']}")
        return

    params: dict = {}
    if args.params:
        if os.path.isfile(args.params):
            with open(args.params, encoding="utf-8") as f:
                params.update(json.load(f))
        else:
            params.update(json.loads(args.params))
    if args.qubits:
        params["qubits"] = args.qubits
    for item in args.set:
        key, _, value = item.partition("=")
        params[key] = _parse_value(value)
    params.setdefault("qubits", list(sess.device_state()))

    result = sess.run(args.experiment, params, update=not args.no_update, tags=args.tags, note=args.note)
    print(json.dumps(result, indent=2))
    if "data_path" in result:
        print(f"\nsaved: {result['data_path']}")


if __name__ == "__main__":
    main()
