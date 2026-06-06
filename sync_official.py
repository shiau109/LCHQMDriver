#!/usr/bin/env python3
"""
Sync official qua-libs calibration files into this repo by COPYING them
(vendoring), so the repo is self-contained and the copies are tracked in git.

Why copy instead of symlink:
  - qualibrate scans the calibration library folder non-recursively and requires
    each node to be a real ``.py`` file containing a ``QualibrationNode`` instance
    (see qualibrate/qualibration_node.py ``scan_folder_for_instances``). The files
    must physically live in ``calibrations/`` either way.
  - Copies need no Administrator rights (Windows symlinks do), are portable across
    machines, avoid git's directory-symlink quirks, and make every upstream update
    a reviewable ``git diff`` instead of an invisible change.

Update routine (roughly every couple of months):
    cd <qua-libs_official> && git pull
    cd <this repo> && python sync_official.py
    git diff            # review upstream changes, esp. calibration_utils/
    git commit -am "chore: sync official qua-libs @ <date>"

Configuration is read from 'calibration_links.toml' in the same directory. The
official source location can be overridden with the QUA_LIBS_OFFICIAL environment
variable (takes precedence over ``source_base`` in the toml).

Usage:
    python sync_official.py

The vendored files are OFFICIAL code: do NOT edit them in place. Edit upstream and
re-sync, or override behaviour in your own ``LCH_*`` / ``customized/`` code.
"""

import os
import sys
import json
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Handle TOML parsing for different Python versions
try:
    import tomllib  # Python 3.11+
except ImportError:
    try:
        import tomli as tomllib  # pip install tomli for Python < 3.11
    except ImportError:
        tomllib = None

# Environment variable that overrides ``source_base`` from the config file.
SOURCE_ENV_VAR = "QUA_LIBS_OFFICIAL"
STAMP_FILE = "official_sync.json"
IGNORE_PATTERNS = shutil.ignore_patterns("__pycache__", "*.pyc", "*.pyo")


def load_config(config_path: Path) -> dict:
    """Load configuration from TOML file."""
    if not config_path.exists():
        print(f"ERROR: Config file not found: {config_path}")
        print("Please create 'calibration_links.toml' with your source definitions.")
        sys.exit(1)

    if tomllib is None:
        print("ERROR: TOML parser not available.")
        print("For Python < 3.11, install tomli: pip install tomli")
        sys.exit(1)

    with open(config_path, "rb") as f:
        return tomllib.load(f)


def resolve_source_base(config: dict) -> Path:
    """Resolve the official source base: env var wins, else config ``source_base``."""
    env_value = os.environ.get(SOURCE_ENV_VAR)
    if env_value:
        print(f"Using {SOURCE_ENV_VAR}={env_value}")
        return Path(env_value)
    source_base = config.get("source_base", "")
    if not source_base:
        print(f"ERROR: no source found. Set ${SOURCE_ENV_VAR} or 'source_base' in config.")
        sys.exit(1)
    return Path(source_base)


def remove_existing(path: Path) -> None:
    """Remove a file, directory, or symlink (including a directory symlink)."""
    if path.is_symlink():
        # Remove the link itself, never follow it.
        if os.path.isdir(path):
            os.rmdir(path)  # directory symlink (Windows)
        else:
            path.unlink()
    elif path.is_dir():
        shutil.rmtree(path)
    elif path.exists():
        path.unlink()


def copy_file(src: Path, dst: Path) -> bool:
    """Copy a single file, replacing whatever is at dst (file or stale symlink)."""
    try:
        remove_existing(dst)
        shutil.copy2(src, dst)
        return True
    except OSError as e:
        print(f"   FAILED: {e}")
        return False


def mirror_dir(src: Path, dst: Path) -> bool:
    """Replace dst with a fresh copy of src (excluding caches)."""
    try:
        remove_existing(dst)
        shutil.copytree(src, dst, ignore=IGNORE_PATTERNS)
        return True
    except OSError as e:
        print(f"   FAILED: {e}")
        return False


def get_py_files(folder: Path) -> list:
    """Get all .py files in a folder (non-recursive)."""
    if not folder.exists():
        return []
    return sorted(f for f in folder.iterdir() if f.is_file() and f.suffix == ".py")


def get_subfolders(folder: Path) -> list:
    """Get all subfolders in a folder (non-recursive), skipping dunder dirs."""
    if not folder.exists():
        return []
    return sorted(d for d in folder.iterdir() if d.is_dir() and not d.name.startswith("__"))


def read_prior_vendored(script_dir: Path) -> list:
    """Read the list of paths vendored by the previous sync, from the stamp."""
    stamp_path = script_dir / STAMP_FILE
    if not stamp_path.exists():
        return []
    try:
        data = json.loads(stamp_path.read_text(encoding="utf-8"))
        return list(data.get("vendored_paths", []))
    except (ValueError, OSError):
        return []


def prune_stale(script_dir: Path, prior: list, current: set) -> list:
    """
    Remove paths vendored by a previous sync that the current sync no longer
    produces (upstream renamed/removed them). Only ever touches paths this script
    itself vendored before -- never LCH_*/customized files.
    """
    removed = []
    for rel in prior:
        if rel in current:
            continue
        # Safety: only prune inside the two vendored roots.
        if not (rel.startswith("calibrations/") or rel.startswith("calibration_utils/")):
            continue
        path = script_dir / rel
        if path.exists() or path.is_symlink():
            remove_existing(path)
            removed.append(rel)
            print(f"   PRUNED stale: {rel}")
    return removed


def source_git_commit(source_base: Path) -> str:
    """Best-effort short git commit of the official checkout, for the stamp."""
    try:
        out = subprocess.run(
            ["git", "-C", str(source_base), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=10,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except Exception:
        pass
    return "unknown"


def write_stamp(script_dir: Path, source_base: Path, copied: dict, vendored_paths: list) -> None:
    """Record which official version was vendored, for traceability and pruning."""
    stamp = {
        "synced_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_base": str(source_base),
        "source_git_commit": source_git_commit(source_base),
        "calibration_files": copied["files"],
        "calibration_utils_dirs": copied["dirs"],
        "vendored_paths": sorted(vendored_paths),
    }
    (script_dir / STAMP_FILE).write_text(json.dumps(stamp, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {STAMP_FILE} (official commit {stamp['source_git_commit'][:8]}).")


def main() -> int:
    script_dir = Path(__file__).parent.resolve()
    config = load_config(script_dir / "calibration_links.toml")
    source_base = resolve_source_base(config)

    calibrations_source = config.get("calibrations_source", [])
    if isinstance(calibrations_source, str):
        calibrations_source = [calibrations_source] if calibrations_source else []
    calibration_utils_source = config.get("calibration_utils_source", [])
    if isinstance(calibration_utils_source, str):
        calibration_utils_source = [calibration_utils_source] if calibration_utils_source else []

    print()
    print("=" * 60)
    print("Vendoring official calibration files (copy, not symlink)")
    print(f"Source base: {source_base}")
    print("=" * 60)

    if not source_base.exists():
        print(f"ERROR: Source base does not exist: {source_base}")
        print(f"Set ${SOURCE_ENV_VAR} or fix 'source_base' in calibration_links.toml.")
        return 1

    success_count = 0
    fail_count = 0
    copied = {"files": 0, "dirs": 0}
    vendored_paths = []  # relative paths produced by this run, for the stamp + pruning
    prior_paths = read_prior_vendored(script_dir)

    # === calibrations (files) ===
    if calibrations_source:
        print("\n=== CALIBRATIONS (files) ===")
        (script_dir / "calibrations").mkdir(exist_ok=True)
        index = 0
        for source_rel in calibrations_source:
            src_path = source_base / source_rel
            print(f"\nSource: {src_path}")
            if not src_path.exists():
                print("   ERROR: Source folder does not exist!")
                continue
            py_files = get_py_files(src_path)
            if not py_files:
                print("   No .py files found.")
                continue
            print(f"   Found {len(py_files)} .py file(s)")
            for target in py_files:
                index += 1
                dst = script_dir / "calibrations" / target.name
                if copy_file(target, dst):
                    success_count += 1
                    copied["files"] += 1
                    vendored_paths.append(f"calibrations/{target.name}")
                else:
                    fail_count += 1

    # === calibration_utils (directories) ===
    if calibration_utils_source:
        print("\n=== CALIBRATION_UTILS (directories) ===")
        (script_dir / "calibration_utils").mkdir(exist_ok=True)
        for source_rel in calibration_utils_source:
            src_path = source_base / source_rel
            print(f"\nSource: {src_path}")
            if not src_path.exists():
                print("   ERROR: Source folder does not exist!")
                continue
            subfolders = get_subfolders(src_path)
            if not subfolders:
                print("   No subfolders found.")
                continue
            print(f"   Found {len(subfolders)} subfolder(s)")
            for target in subfolders:
                dst = script_dir / "calibration_utils" / target.name
                if mirror_dir(target, dst):
                    success_count += 1
                    copied["dirs"] += 1
                    vendored_paths.append(f"calibration_utils/{target.name}")
                else:
                    fail_count += 1

    # Prune files a previous sync vendored that upstream has since renamed/removed.
    print("\n=== PRUNE STALE (from previous sync) ===")
    removed = prune_stale(script_dir, prior_paths, set(vendored_paths))
    if not removed:
        print("   Nothing to prune.")

    print("\n=== STAMP ===")
    write_stamp(script_dir, source_base, copied, vendored_paths)

    print()
    print("=" * 60)
    print(f"Done. Copied: {success_count}, Failed: {fail_count}, Pruned: {len(removed)}")
    print(f"({copied['files']} node files, {copied['dirs']} util dirs)")
    print("Review with `git diff`, then commit the vendored update.")
    print("=" * 60)

    return 0 if fail_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
