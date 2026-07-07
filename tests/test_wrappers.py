"""Backward-compat surface: the scripts/ wrappers + the qm backend entry point.

The real CLI coverage lives in SCQO/tests (test_cli_*.py); this smoke test proves
the QM-side glue with the v0.5.0 factory signature build_backend(cfg, setup).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def _env(tmp_path: Path) -> dict:
    data_root = tmp_path / "data"
    (data_root / "simdev").mkdir(parents=True)
    (data_root / "simdev" / "cooldowns.toml").write_text(
        '[cd1]\nstart = 2026-07-01\n[[cd1.setup]]\nsince = 2026-07-01\nbackend = "simulated"\n',
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text(
        f"[lab]\ndevice = \"simdev\"\ndata_root = '{data_root.as_posix()}'\n", encoding="utf-8"
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


def test_backend_entry_point_resolves_and_guards_fire(tmp_path):
    """The qm factory loads (vendor-free import); the pull-guard fires BEFORE any
    QUAM state is touched; missing canonical files are named — no hardware needed."""
    from importlib.metadata import entry_points

    import pytest

    from scqo.labconfig import LabConfig

    eps = {ep.name: ep for ep in entry_points(group="scqo.backends")}
    assert "qm" in eps, "reinstall the editable (uv pip install -e . --no-deps) to register entry points"
    factory = eps["qm"].load()

    empty = tmp_path / "empty"
    empty.mkdir()
    setup = {"since": "2026-07-01", "backend": "qm", "instrument_config": str(empty)}

    push_cfg = LabConfig(state_sync="push")
    with pytest.raises(SystemExit, match="pull"):
        factory(push_cfg, setup)  # state-authority guard, before any file access

    pull_cfg = LabConfig(state_sync="pull")
    with pytest.raises(SystemExit, match="state.json"):
        factory(pull_cfg, setup)  # canonical QUAM files required in the folder

    with pytest.raises(SystemExit, match="qm"):
        factory(pull_cfg, {"backend": "qblox"})  # wrong family refused
