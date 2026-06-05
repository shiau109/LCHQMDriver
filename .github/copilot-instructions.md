# LCHQMDriver — Copilot Instructions

## Project Overview
Superconducting qubit calibration system for Quantum Machines OPX1000 hardware (MW-FEM + LF-FEM), built on three layers: **qm-qua** → **quam** → **qualibrate** (see Workspace Packages for details).

## Folder Roles

| Folder | Role | Editable? |
|--------|------|-----------|
| `quam_config/` | QUAM class definition + scripts to generate initial config for `quam_state/`. `my_quam.py` is the entrypoint class used everywhere. | Yes |
| `quam_state/` | Serialized instrument config files (`state.json`, `wiring.json`). Not code. | Generated output |
| `calibrations/` | Calibration node scripts shown in the qualibrate GUI. Mix of **symlinked official** nodes and **custom `LCH_*`** nodes. | Only `LCH_*` files |
| `calibration_utils/` | Exists only to satisfy relative imports from symlinked official nodes. | No (symlinked) |
| `customized/` | All lab-specific code: custom pulses, macros, QUAM component extensions, and calibration node logic. | Yes |
| `data/` | Data storage only. No code. Skip. | N/A |

## Custom vs Official Nodes

**Official nodes** (symlinked from `qua-libs`):
- `calibrations/<name>.py` → symlinked, do NOT edit
- `calibration_utils/<name>/` → symlinked, do NOT edit

**Custom LCH nodes** (this lab's own code):
- `calibrations/LCH_<name>.py` → calibration script (GUI entry point)
- `customized/node/LCH_<name>/` → only `parameters.py` is required (for qualibrate GUI). Add `analysis.py` / `plotting.py` only when the logic is complex enough to extract from the calibration script.
- `customized/components/` → shared pulse shapes, macros, QUAM extensions

## Key Entrypoints
- `quam_config/my_quam.py` → defines the `Quam(FluxTunableQuam)` class imported by every calibration node and config script. The custom-type bindings (`qubit_type = ChargeTunableTransmon`, `qubit_pair_type = LCH_FluxTunableTransmonQCQPair`) are **toggled in/out per experiment** — they are intentionally commented out by default and uncommented only when a run needs the custom charge-tunable types. Do NOT treat either state as "wrong"; read the live class body to see what is active, and ask before flipping it.
- `customized/quam_builder/` → custom qubit type `ChargeTunableTransmon`
- `customized/qubit_pair/` → custom qubit pair `LCH_FluxTunableTransmonQCQPair`

## Operational Notes (verified against the working tree)
- **Symlinks are auto-generated, not committed.** Official `calibrations/<name>.py` and `calibration_utils/<name>/` are real on-disk symlinks created by `create_calibration_links.py` from `calibration_links.toml`, pointing at an external `qua-libs_official` checkout. They are listed in `.gitignore`, so `git ls-files` shows no symlinks — only `LCH_*` and other in-tree files are tracked.
- **`calibrations/offline_graph/`** holds `LCH_graph_*.py` post-processing/graph scripts. Editable lab code, same `LCH_` convention as nodes.
- **Run / setup** (Windows, conda env `LCHQM`):
  - `start_server.bat` → `qualibrate start` (launches the GUI server)
  - `setup_qualibrate_config.bat` → `setup-qualibrate-config`
- **Packaging:** `pyproject.toml` — Python `>=3.9,<3.13`, black `line-length = 120`. Wheel packages: `calibrations`, `quam_config`, `calibration_utils`.

## Workspace Packages (Read-Only)
The following dependency packages are available in the workspace for reference. Do NOT modify them.
- **qm** — Low-level QUA instrument control API
- **quam** — Hardware abstraction layer (QUAM core)
- **quam_builder** — QUAM state generation utilities
- **qualibrate** — Calibration GUI framework

**Expected workspace setup:** This is a multi-root workspace. If any of the above packages are missing from the workspace folders, inform the user. They should be added via File → Add Folder to Workspace from the conda environment's `site-packages/` directory.

## Rules for Copilot

1. **Do NOT edit symlinked files.** Non-`LCH_` files in `calibrations/` and everything in `calibration_utils/` are symlinks from the official `qua-libs` repo.
2. **Always present a plan before modifying code.** Only modify code after the user gives explicit approval.
3. **Editable code lives in:** `customized/`, `quam_config/`, and `LCH_*` files in `calibrations/`.
4. **Skip `data/`** — data storage only, no code to read or modify.
5. **Flag critical dependencies.** When creating or modifying customized code, if any dependency (from `qm`, `quam`, `quam_builder`, `qualibrate`, or other packages) is critical to the implementation, explicitly tell the user which dependencies are involved.
6. **Check workspace completeness.** If the workspace is missing expected folders (e.g., `qm`, `quam`, `quam_builder`, `qualibrate`), notify the user so they can add them on the current device.
7. **Report conflicts.** If existing code contradicts these instructions (e.g., an LCH node has unnecessary analysis.py/plotting.py files, or imports don't follow the expected pattern), inform the user before making changes.
