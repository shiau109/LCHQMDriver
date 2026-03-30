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
- `quam_config/my_quam.py` → defines `Quam(FluxTunableQuam)` with `qubit_type = ChargeTunableTransmon`. Imported by every calibration node and config script.
- `customized/quam_builder/` → custom qubit type `ChargeTunableTransmon`
- `customized/qubit_pair/` → custom qubit pair `LCH_FluxTunableTransmonQCQPair`

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
