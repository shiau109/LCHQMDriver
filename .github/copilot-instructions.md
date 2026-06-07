# LCHQMDriver — Copilot Instructions

## Project Overview
Superconducting qubit calibration system for Quantum Machines OPX1000 hardware (MW-FEM + LF-FEM), built on three layers: **qm-qua** → **quam** → **qualibrate** (see Workspace Packages for details).

## Related — shared experiment API (planned)
This repo is intended to become the **QM reference backend** for **`scqo`**, a vendor-neutral protocol/parameters API shared with the Qblox driver (`D:\github\SCQO`, `D:\github\LCHQBDriver`). The neutral layer lets the same experiment run on either instrument — manually or via an AI agent — through one `Session` (`catalog()` / `run()` / `device_state()`, all JSON in/out). **Not yet wired up here:** there is no `QMBackend` in this repo today; the QM nodes still run directly on qualibrate. See `SCQO\CLAUDE.md` for the full design before adding any scqo integration.

## Folder Roles

| Folder | Role | Editable? |
|--------|------|-----------|
| `quam_config/` | QUAM class definition + scripts to generate initial config for `quam_state/`. `my_quam.py` is the entrypoint class used everywhere. | Yes |
| `quam_state/` | Serialized instrument config files (`state.json`, `wiring.json`). Not code. | Generated output |
| `calibrations/` | Calibration node scripts shown in the qualibrate GUI. Mix of **vendored official** nodes (copied in by `sync_official.py`) and **custom `LCH_*`** nodes. | Only `LCH_*` files |
| `calibration_utils/` | Vendored official support code (copied in), satisfies relative imports from official nodes. | No (regenerate via `sync_official.py`) |
| `customized/` | All lab-specific code: custom pulses, macros, QUAM component extensions, and calibration node logic. | Yes |
| `data/` | Data storage only. No code. Skip. | N/A |

## Custom vs Official Nodes

**Official nodes** (vendored from `qua-libs` via `sync_official.py`):
- `calibrations/<name>.py` → copied-in, do NOT edit (overwritten on next sync)
- `calibration_utils/<name>/` → copied-in, do NOT edit (overwritten on next sync)

**Custom LCH nodes** (this lab's own code):
- `calibrations/LCH_<name>.py` → calibration script (GUI entry point)
- `customized/node/LCH_<name>/` → only `parameters.py` is required (for qualibrate GUI). Add `analysis.py` / `plotting.py` only when the logic is complex enough to extract from the calibration script.
- `customized/components/` → shared pulse shapes, macros, QUAM extensions

## Key Entrypoints
- `quam_config/my_quam.py` → defines the `Quam(FluxTunableQuam)` class imported by every calibration node and config script. The custom-type bindings (`qubit_type = ChargeTunableTransmon`, `qubit_pair_type = LCH_FluxTunableTransmonQCQPair`) are **toggled in/out per experiment** — they are intentionally commented out by default and uncommented only when a run needs the custom charge-tunable types. Do NOT treat either state as "wrong"; read the live class body to see what is active, and ask before flipping it.
- `customized/quam_builder/` → custom qubit type `ChargeTunableTransmon`
- `customized/qubit_pair/` → custom qubit pair `LCH_FluxTunableTransmonQCQPair`

## Operational Notes (verified against the working tree)
- **Official code is VENDORED (copied), and committed.** Official `calibrations/<name>.py` and `calibration_utils/<name>/` are real files copied in by `sync_official.py` from `calibration_links.toml` (source = an external `qua-libs_official` checkout, overridable via the `QUA_LIBS_OFFICIAL` env var). They ARE tracked in git, so the repo is self-contained — clone + `pip install -e .` runs official nodes with no external checkout present. `official_sync.json` records which upstream commit is currently vendored. **Do not edit vendored official files in place; do not symlink them.** Why copy: qualibrate scans the library folder non-recursively and needs each node to be a real `.py` file (see `qualibrate/qualibration_node.py` `scan_folder_for_instances`), and copies avoid the Windows-admin requirement, git directory-symlink quirks, and the old cp950 encoding patch (recent qualibrate already reads node files as UTF-8).
- **Updating official (~every 2 months):** `git pull` in the `qua-libs_official` checkout → `python sync_official.py` → `git diff` (review upstream changes, especially `calibration_utils/` that `LCH_*` nodes import) → commit. The custom `LCH_*` files and `customized/` have distinct names and are never touched by the sync.
- **`calibrations/offline_graph/`** holds `LCH_graph_*.py` post-processing/graph scripts. Editable lab code, same `LCH_` convention as nodes. qualibrate does not list them (it scans `calibrations/` non-recursively); run them manually.
- **Run / setup** (conda env `LCHQM_test`; the launcher targets this env):
  - `qm.bat` (Windows) / `qm.command` (macOS/Linux) → wrappers that activate the env and run `qualibrate start` (launches the GUI server). These replaced the old Windows-only `start_server.bat` / `setup_qualibrate_config.bat`.
  - `setup-qualibrate-config` → one-time qualibrate config setup.
- **Packaging:** `pyproject.toml` — Python `>=3.10,<3.13`, black `line-length = 120`. Wheel packages: `calibrations`, `calibration_utils`, `quam_config`, `customized`.
- **External analysis dependency.** LCH analysis nodes lazily import `scqat` (`D:\github\SCqubit-analysis-tool`, the lab's analysis tool that **replaced** the older `qcat`/`D:\github\QCAT`), installed editable. It is **not declared in `pyproject.toml`** and must be installed in the runtime env — now present (editable) in both `LCHQM` and `LCHQM_test` (the launcher env; verified 2026-06-07) — or those nodes raise `ImportError` at plot time. Official (non-`LCH_`) nodes do not depend on it and run regardless. The qcat→scqat migration of the active `LCH_*` nodes is complete (`calibrations/exclude/` still references qcat); see `ANALYSIS_MIGRATION.md`.

## Workspace Packages (Read-Only)
The following dependency packages are available in the workspace for reference. Do NOT modify them.
- **qm** — Low-level QUA instrument control API
- **quam** — Hardware abstraction layer (QUAM core)
- **quam_builder** — QUAM state generation utilities
- **qualibrate** — Calibration GUI framework

**Expected workspace setup:** This is a multi-root workspace. If any of the above packages are missing from the workspace folders, inform the user. They should be added via File → Add Folder to Workspace from the conda environment's `site-packages/` directory.

## Rules for Copilot

1. **Do NOT edit vendored official files.** Non-`LCH_` files in `calibrations/` and everything in `calibration_utils/` are official `qua-libs` code copied in by `sync_official.py`. Edits would be overwritten on the next sync — change behavior in `LCH_*` / `customized/` instead, or update upstream and re-sync.
2. **Always present a plan before modifying code.** Only modify code after the user gives explicit approval.
3. **Editable code lives in:** `customized/`, `quam_config/`, and `LCH_*` files in `calibrations/`.
4. **Skip `data/`** — data storage only, no code to read or modify.
5. **Flag critical dependencies.** When creating or modifying customized code, if any dependency (from `qm`, `quam`, `quam_builder`, `qualibrate`, or other packages) is critical to the implementation, explicitly tell the user which dependencies are involved.
6. **Check workspace completeness.** If the workspace is missing expected folders (e.g., `qm`, `quam`, `quam_builder`, `qualibrate`), notify the user so they can add them on the current device.
7. **Report conflicts.** If existing code contradicts these instructions (e.g., an LCH node has unnecessary analysis.py/plotting.py files, or imports don't follow the expected pattern), inform the user before making changes.
