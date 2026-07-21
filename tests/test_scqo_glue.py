"""Driver-side scqo glue: the `scqo` CLI works in THIS venv + the qm factory.

The real CLI coverage lives in SCQO/tests (test_cli_*.py); this smoke test proves
the QM-side glue with build_backend(cfg, setup) — the setup is a NAMED record
(backend + note, plus the DERIVED "instrument_config" vendor folder injected by
scqo since v0.9). The v0.4-era scripts/ wrapper layer and the launcher stubs were
retired in v0.7.0.
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
        '[cd1]\nstart = 2026-07-01\n[cd1.setup.practice]\nbackend = "simulated"\n',
        encoding="utf-8",
    )
    # Post-cutover a configured device REQUIRES a component roster.
    (data_root / "simdev" / "components.toml").write_text(
        'schema = 1\n'
        '[components.q0]\n'
        'physical   = "FixedTransmon"\n'
        'instrument = "ReadableTransmon"\n'
        'operations = ["rx", "readout"]\n'
        '[components.q0_res]\n'
        'physical = "Resonator"\n'
        '[components.q0_ro]\n'
        'physical = "ReadoutLine"\n'
        'members  = { transmon = "q0", resonator = "q0_res" }\n'
        '[components.q0_xy]\n'
        'physical = "XYControl"\n'
        'members  = { transmon = "q0" }\n',
        encoding="utf-8",
    )
    config = tmp_path / "config.toml"
    config.write_text(
        f"[lab]\ndevice = \"simdev\"\ndata_root = '{data_root.as_posix()}'\n", encoding="utf-8"
    )
    return {**os.environ, "SCQO_CONFIG": str(config), "SCQO_USER_CONFIG": "none"}


def test_scqo_run_end_to_end(tmp_path):
    proc = subprocess.run(
        [sys.executable, "-m", "scqo.cli", "run", "resonator_spectroscopy", "--targets", "q0"],
        capture_output=True, text=True, env=_env(tmp_path), cwd=REPO,
    )
    assert proc.returncode == 0, proc.stderr
    result = json.loads(proc.stdout.split("\nsaved:")[0])
    assert result["outcomes"] == {"q0": "successful"}


def test_field_catalog_matches_implementation():
    """The declared field catalog cannot drift: per category, bindings + declared
    unrealized fields cover EXACTLY scqo's pushed fields (a new core field fails
    here until this driver binds or declares it — the combo-release alarm),
    coupled names are real sibling fields, the vendor-only inventory collides
    with no tracked field, and the module is pure data (importable without
    qm/quam — enforced on its import statements)."""
    import ast

    from scqo.categories import field_categories, pushed_fields

    from customized.scqo import fieldmap

    # BOTH declared categories (ReadableTransmon + TransmonPair) drift-checked
    assert set(fieldmap.FIELD_BINDINGS) == {"ReadableTransmon", "TransmonPair"}
    for cat, bindings in fieldmap.FIELD_BINDINGS.items():
        unrealized = fieldmap.UNREALIZED.get(cat, {})
        assert set(bindings) | set(unrealized) == set(pushed_fields(cat)), cat
        assert not set(bindings) & set(unrealized)  # bound XOR declared out
        for name, binding in bindings.items():
            assert binding.path, f"{name}: empty vendor path"
            assert set(binding.coupled) <= set(bindings) - {name}, name
    for cat, fields in fieldmap.UNREALIZED.items():
        for name, u in fields.items():
            assert (u.category, u.field) == (cat, name) and u.reason, name
    assert not set(fieldmap.VENDOR_ONLY) & set(field_categories())
    assert all(v.path and v.doc for v in fieldmap.VENDOR_ONLY.values())

    # every entry carries a valid placement-rule kind; unique entries must state
    # the lock-in fact (no counterpart on the other backend)
    from scqo.fieldmap import VENDOR_ONLY_KINDS

    for name, v in fieldmap.VENDOR_ONLY.items():
        assert v.kind in VENDOR_ONLY_KINDS, name
        if v.kind == "unique":
            assert "no qblox counterpart" in v.doc.lower(), name

    tree = ast.parse(Path(fieldmap.__file__).read_text(encoding="utf-8"))
    imported = {
        name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for name in ([a.name for a in node.names] if isinstance(node, ast.Import)
                     else [node.module])
    }
    assert imported <= {"__future__", "scqo.fieldmap"}, imported

    # the backend class serves exactly the declared catalog (methods are pure)
    from customized.scqo.backend import QMBackend

    assert QMBackend.field_bindings(None) == fieldmap.FIELD_BINDINGS
    assert QMBackend.unrealized(None) == fieldmap.UNREALIZED
    assert QMBackend.vendor_only(None) == fieldmap.VENDOR_ONLY


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
    setup = {"backend": "qm", "instrument_config": str(empty)}

    push_cfg = LabConfig(state_sync="push")
    with pytest.raises(SystemExit, match="pull"):
        factory(push_cfg, setup)  # state-authority guard, before any file access

    pull_cfg = LabConfig(state_sync="pull")
    with pytest.raises(SystemExit, match="state.json"):
        factory(pull_cfg, setup)  # canonical QUAM files required in the folder

    with pytest.raises(SystemExit, match="qm"):
        factory(pull_cfg, {"backend": "qblox"})  # wrong family refused
