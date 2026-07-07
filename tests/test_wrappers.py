"""Backward-compat surface: the scripts/ wrappers + the qm backend entry point.

The real CLI coverage lives in SCQO/tests (test_cli_*.py); this smoke test proves
the QM-side glue only. NOTE: the built-in simulated demo device is q0/q1 since the
CLI consolidation (this repo's old scripts used q1/q2 demo names — fresh-start).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _env(tmp_path: Path) -> dict:
    config = tmp_path / "config.toml"
    config.write_text(
        f"[lab]\nbackend = \"simulated\"\ndata_root = '{(tmp_path / 'data').as_posix()}'\n",
        encoding="utf-8",
    )
    return {**os.environ, "SCQO_CONFIG": str(config), "SCQO_USER_CONFIG": "none"}


def test_wrapper_runs_end_to_end(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "run_experiment.py"),
         "resonator_spectroscopy", "--qubits", "q0"],
        capture_output=True, text=True, env=_env(tmp_path), cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.split("\nsaved:")[0])
    assert result["outcomes"] == {"q0": "successful"}


def test_regenerated_stub_help(tmp_path):
    proc = subprocess.run(
        [sys.executable, str(REPO / "scripts" / "experiments" / "resonator_spectroscopy.py"), "--help"],
        capture_output=True, text=True, env=_env(tmp_path), cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    assert "frequency_span_hz" in proc.stdout  # schema epilog through scqo.cli


def test_backend_entry_point_resolves_and_pull_guard_fires(tmp_path, monkeypatch):
    """The qm factory loads (vendor-free import) and the state-authority guard now
    fires BEFORE any QUAM state is touched — no hardware or state file needed."""
    from importlib.metadata import entry_points

    import pytest

    from scqo import load_lab_config

    eps = {ep.name: ep for ep in entry_points(group="scqo.backends")}
    assert "qm" in eps, "reinstall the editable (uv pip install -e . --no-deps) to register entry points"
    factory = eps["qm"].load()

    monkeypatch.setenv("SCQO_USER_CONFIG", "none")  # hermetic: no real ~/.scqo/user.toml
    config = tmp_path / "config.toml"
    config.write_text('[lab]\nbackend = "qm"\nstate_sync = "push"\n', encoding="utf-8")
    cfg = load_lab_config(str(config))
    with pytest.raises(SystemExit, match="pull"):
        factory(cfg)
