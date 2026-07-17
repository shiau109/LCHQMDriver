# LCHQMDriver — project guide

## Project Overview
Superconducting qubit calibration system for Quantum Machines OPX1000 hardware (MW-FEM + LF-FEM), built on three layers: **qm-qua** → **quam** → **qualibrate** (see Workspace Packages for details).

## Related — shared experiment API
This repo is the **QM reference backend** for **`scqo`**, the vendor-neutral protocol/parameters API shared with the Qblox driver, so the same experiment runs on either instrument through one `Session`. The QM backend lives in `customized/scqo/`; qualibrate's `calibrations/` path runs the same probes directly (see **Probes vs shells**). Design, the `Session` contract, and cross-repo terminology (Experiment = probe + estimator) live in `SCQO\CLAUDE.md`; this repo's analysis nodes consume scqat **estimators** (`scqat.estimators`).

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
- `customized/node/LCH_<name>/` → qualibrate-side code for the node: `parameters.py` (GUI schema; required unless the node reuses a vendored `Parameters`), plus the node's `analysis.py` (scqat adapter) and `update.py` (state-update policy) once extracted. See **Probes vs shells** below for what goes where.
- `customized/probes/<name>.py` → the instrument-acquisition half, shared with scqo. See **Probes vs shells**.
- `customized/components/` → shared pulse shapes, macros, QUAM extensions

## Probes vs shells (`customized/probes/` + `customized/node/`)
LCH nodes are being refactored so qualibrate is a thin shell, not the architecture. The split is by
**who calls the code**, which is also an **import rule**:

| Folder | Side | May import |
|---|---|---|
| `customized/probes/<name>.py` | acquisition: params in → `xr.Dataset` out. Called by BOTH the qualibrate shell and the scqo `QMBackend` (`customized/scqo/`, live since v0.1.x). | qm.qua, quam, qualang_tools, `qualibration_libs.core`/`.data`. **NEVER** qualibrate, scqo, or scqat — probes acquire, they never fit. |
| `customized/node/LCH_<name>/` | the qualibrate node: `parameters.py` (GUI schema), `analysis.py` (scqat estimate adapter), `update.py` (pure `compute_update` + `apply_update` state-update policy). | qualibrate, vendored official params, scqat (lazy, inside `fit`). |
| `calibrations/LCH_<name>.py` | qualibrate shell: `@node.run_action` glue (~3–10 lines each) unpacking `node.parameters` into probe/analysis/update calls. | everything. |

Shared probe helpers (`select_qubits` — the node-free `get_qubits`; `acquire` — the shared
execute-and-fetch) live in `customized/probes/_lib.py`.

**Why this split:** the scqo contract is that a driver contributes only `probe()`; estimate/update are
inherited from `scqo.experiments` + scqat. So the probe is the one piece both orchestrators share and
must stay framework-free, while analysis/update are qualibrate-path adapters. ("probes" matches scqo's
canonical vocabulary and avoids colliding with scqo's `Experiment`.)

**Two orchestration paths, one estimator implementation:**
- **scqo-driven** (live, migrated experiments only): scqo `Session` owns the probe→estimate→update
  lifecycle, data saving, and run history; it calls `customized/probes/<name>.py` and runs the scqat
  estimator itself.
- **QM-only** (today): qualibrate owns orchestration, saving, GUI approval; the LCH node calls its own
  `customized/node/LCH_<name>/{analysis,update}`. Vendored **official** nodes keep QM's built-in
  analysis and never run under scqo.
- In **both** paths the estimator *implementation* lives once in scqat — only the calling shell differs.

**Lab-tuned parameter defaults** go in the lab `Parameters` subclass (e.g. `LCHNodeSpecificParameters`
in `customized/node/LCH_power_rabi/parameters.py`), **never** in vendored `calibration_utils/` (which
`sync_official.py` reverts).

**Readout-power punchout probes:** both `resonator_spectroscopy_power_chain` (sweeps full-scale
power) and `resonator_spectroscopy_power_amp` (sweeps amplitude prefactors) take absolute-dBm inputs
(`min/max_power_dbm`).

**Migration status:** qualibrate-node migration is in progress; the `customized/` split into a
standalone QM-backend repo (symmetric with LCHQBDriver) is decided but deferred until migration
completes — the shells→probes import rule above is the boundary the split will cut along.

### State authority during the transition (scqo `state_sync` rule)
Two writers exist for QUAM today: unmigrated qualibrate nodes (write QUAM directly) and scqo's
`RecordingDevice` (owns its own state JSON). To prevent a stale scqo state file from clobbering
fresher QUAM calibrations at startup, **QM sessions MUST run `state_sync="pull"`** (scqo's default):
the vendor wins at startup, scqo loads only its change history, and pushes only values it freshly
measures. The migration finish line is flipping this device to `"push"` — do that only when no
qualibrate node writes QUAM anymore. (`customized/scqo/backend_factory.py` enforces
this — the guard fires before any QUAM state is loaded.)
**Which QUAM state loads** is decided by the device's cooldown setup alone: the SELECTED
`[<cycle>.setup.<name>]` block's vendor folder — DERIVED since scqo v0.9 as
`<device>/<cycle>/<name>/backend_config/` (no path key in the registry; users pick a setup with
`scqo user --setup <name>`, a single-setup cycle auto-selects) — must hold `state.json` +
`wiring.json` under exactly those canonical names — never rely on `~/.qualibrate` resolution for
scqo sessions; keep qualibrate's own `[quam] state_path` pointed at the same folder on machines
that run both stacks (re-point it each new cooldown).

### scqo student surface
Students use the **`scqo` command** (`run/find/accept/tag/state/user/device/doctor`) from any
directory in `.venv-qm`, selecting a sample and setup with
`scqo user --device <name> [--setup <name>]` (written to `~/.scqo/user.toml`); `scqo run <name>` is
the one way to run an experiment (never add per-command wrappers or launcher stubs). This repo
contributes `customized/scqo/backend_factory.py`, registered under the `scqo.backends` entry-point
group (name `qm`): `build_backend(cfg, setup)` fires the `state_sync="pull"` guard BEFORE any QUAM
state is touched, then loads the setup's vendor folder (`setup["instrument_config"]`, injected by
scqo from the registry keys; canonical names `state.json` +
`wiring.json` — the single QUAM-state authority; loud SystemExit when missing). `simulated` is the
practice mode. Only migrated experiments run under scqo here; all other calibrations still run
through the qualibrate GUI (legacy, frozen; do not merge).

The my_quam root-class toggle governs test fixtures too: the `machine` fixture skips when the live
`quam_state/` doesn't match the active root (e.g. flux-tunable pairs under a `FixedFrequencyQuam`
root).

## Key Entrypoints
- `quam_config/my_quam.py` → defines the `Quam(FluxTunableQuam)` class imported by every calibration node and config script. The custom-type bindings (`qubit_type = ChargeTunableTransmon`, `qubit_pair_type = LCH_FluxTunableTransmonQCQPair`) are **toggled in/out per experiment** — they are intentionally commented out by default and uncommented only when a run needs the custom charge-tunable types. Do NOT treat either state as "wrong"; read the live class body to see what is active, and ask before flipping it.
- `customized/quam_builder/` → custom qubit type `ChargeTunableTransmon`
- `customized/qubit_pair/` → custom qubit pair `LCH_FluxTunableTransmonQCQPair`

## Operational Notes (verified against the working tree)
- **Official code is VENDORED (copied), and committed.** Official `calibrations/<name>.py` and `calibration_utils/<name>/` are real files copied in by `sync_official.py` from `calibration_links.toml` (source = an external `qua-libs_official` checkout, overridable via the `QUA_LIBS_OFFICIAL` env var). They ARE tracked in git, so the repo is self-contained — clone + `pip install -e .` runs official nodes with no external checkout present. `official_sync.json` records which upstream commit is currently vendored. **Do not edit vendored official files in place; do not symlink them.** Why copy: qualibrate scans the library folder non-recursively and needs each node to be a real `.py` file (see `qualibrate/qualibration_node.py` `scan_folder_for_instances`), and copies avoid the Windows-admin requirement, git directory-symlink quirks, and the old cp950 encoding patch (recent qualibrate already reads node files as UTF-8).
- **Updating official (~every 2 months):** `git pull` in the `qua-libs_official` checkout → `python sync_official.py` → `git diff` (review upstream changes, especially `calibration_utils/` that `LCH_*` nodes import) → commit. The custom `LCH_*` files and `customized/` have distinct names and are never touched by the sync.
- **`calibrations/offline_graph/`** holds `LCH_graph_*.py` post-processing/graph scripts. Editable lab code, same `LCH_` convention as nodes. qualibrate does not list them (it scans `calibrations/` non-recursively); run them manually.
- **Environments (2026-07-05):** the scqo path runs in the uv venv `D:\github\.venv-qm`,
  rebuildable from `requirements-qm.lock.txt` (exact pins frozen from `LCHQM_test`; see
  SCQO/INSTALL.md §1). Sibling envs: `.venv-view` (data browsing, no instrument libs —
  the lab's daily default) and `.venv-qblox` (Qblox measurement). Conda is being retired
  lab-wide; `qm.bat` already targets `.venv-qm` (`qm.bat conda` = legacy fallback) and
  the conda envs get deleted after one validated qualibrate GUI session.
- **Run / setup** (`qm.bat` activates `.venv-qm`; `qm.bat conda` forces the legacy fallback):
  - `qm.bat` (Windows) / `qm.command` (macOS/Linux) → wrappers that activate the env and run `qualibrate start` (launches the GUI server). These replaced the old Windows-only `start_server.bat` / `setup_qualibrate_config.bat`.
  - `setup-qualibrate-config` → one-time qualibrate config setup.
- **Packaging:** `pyproject.toml` — Python `>=3.10,<3.13`, black `line-length = 120`. Wheel packages: `calibrations`, `calibration_utils`, `quam_config`, `customized`.
- **Tests:** the scqo-glue tests live in `tests/test_scqo_glue.py`; run the suite with `pytest`.
- **External analysis dependency.** LCH analysis nodes lazily import `scqat` (`D:\github\scqat`, the lab's analysis tool that **replaced** the older `qcat`/`D:\github\QCAT`), installed editable. It is **not declared in `pyproject.toml`** and must be installed in the runtime env — now present (editable) in both `LCHQM` and `LCHQM_test` (the launcher env; verified 2026-06-07) — or those nodes raise `ImportError` at plot time. Official (non-`LCH_`) nodes do not depend on it and run regardless. The qcat→scqat migration of the active `LCH_*` nodes is complete (`calibrations/exclude/` still references qcat); see `ANALYSIS_MIGRATION.md`.

## Workspace Packages (Read-Only)
The vendor dependency stack (`qm` QUA control → `quam` hardware abstraction → `quam_builder` → `qualibrate` GUI) is available read-only in the workspace; do NOT modify. For the SC-qubit repo layout see the global workspace map `C:\Users\shiau\.claude\CLAUDE.md`.

## Rules for the AI assistant

1. **Do NOT edit vendored official files.** Non-`LCH_` files in `calibrations/` and everything in `calibration_utils/` are official `qua-libs` code copied in by `sync_official.py`. Edits would be overwritten on the next sync — change behavior in `LCH_*` / `customized/` instead, or update upstream and re-sync.
2. **Always present a plan before modifying code.** Only modify code after the user gives explicit approval.
3. **Editable code lives in:** `customized/`, `quam_config/`, and `LCH_*` files in `calibrations/`.
4. **Skip `data/`** — data storage only, no code to read or modify.
5. **Flag critical dependencies.** When creating or modifying customized code, if any dependency (from `qm`, `quam`, `quam_builder`, `qualibrate`, or other packages) is critical to the implementation, explicitly tell the user which dependencies are involved.
6. **Check workspace completeness.** If the workspace is missing expected folders (e.g., `qm`, `quam`, `quam_builder`, `qualibrate`), notify the user so they can add them on the current device.
7. **Report conflicts.** If existing code contradicts these instructions (e.g., an LCH node has unnecessary analysis.py/plotting.py files, or imports don't follow the expected pattern), inform the user before making changes.
