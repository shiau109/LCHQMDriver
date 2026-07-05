# LCH analysis-package migration: qcat → scqat — COMPLETE (active nodes)

The active `LCH_*` calibration nodes have been migrated off the old `qcat`
analysis package (`D:\github\QCAT`) onto **`scqat`**
(`D:\github\scqat`, top-level import `scqat`). scqat was built
as the deliberate successor to qcat (see scqat's own `MIGRATION.md`).

Done 2026-06-06. Scope: all active nodes + commented-out refs. `calibrations/exclude/`
was intentionally left on qcat (qualibrate does not load it).

## Runtime requirement
`scqat` must be installed (editable) in the env that runs the nodes. It is present
in **`LCHQM`** but **not yet in `LCHQM_test`** (the env the launcher targets) — install
it there, or the migrated `plot_data`/`analyse_data` actions raise `ImportError`.
It is not declared in `pyproject.toml` (local path dependency, same as qcat was).

## What changed

**Tier 1 — parser-only swaps** (`qcat.parser.qm_reader` → `scqat.parsers`, identical
names/signatures, zero behavior change):
`LCH_qubit_spectroscopy_zz`, `LCH_coupler_spectroscopy_dispersive`,
`LCH_qubit_parametric_drive_fixed_time`, `LCH_qubit_parametric_drive_freq_time`,
`LCH_qubit_parametric_drive_freq_time_tomo`, and the leftover parser import in the
already-migrated `LCH_charge_gate_ramsey`.

**Tier 2 — analyzer rewrites** to scqat's stateless `analyzer.analyze(ds, output_dir=None)
→ (results, figs)` contract (replacing qcat's `X(ds)` + `._start_analysis()` /
`._plot_results()`):

| Node | qcat → scqat |
|------|--------------|
| `LCH_Ramsey` | `ramsey.RamseyAnalysis` → `RamseyAnalyzer` |
| `LCH_readout_power` | `readout_power.ROFidelityPower` → `ReadoutPowerFidelityAnalyzer` |
| `LCH_readout_frequency` | `readout_freq.ROFidelityFreq` → `ReadoutFreqFidelityAnalyzer` |
| `LCH_readout_fidelity` | `state_discrimination.StateDiscrimination` → `StateDiscriminationAnalyzer` |
| `LCH_qubit_spectroscopy_vs_ROamp` | `ac_stark_shift.*` → `AcStarkShiftAnalyzer` |

In every Tier-2 node the existing `ds_raw` already carries the variable/coordinate
names scqat expects (`signal`+`idle_time`; `I,Q`+`shot_idx`/`prepared_state`+sweep
coord; `I,Q`+`detuning`+`readout_amp_ratio`), so **no dataset renaming was needed**.

**Tier 3 — commented-out qcat refs** repointed to scqat equivalents (kept commented):
`LCH_charge_gate_readout_power`, `LCH_charge_gate_readout_power_with_ref`,
`LCH_time_dep_rr_photon` (since refactored to the probe structure and renamed
`LCH_qubit_acstark_time`, with `ReadoutPulsePhotonEstimator` now wired in — no longer commented).

## Behavioral reductions accepted (flagged inline in the nodes)
- **`LCH_readout_power`**: scqat's `ReadoutPowerFidelityAnalyzer` does **not** port
  qcat's power-specific linear mean-drift refit (`fit_means_vs_amp_prefactor`). Core
  per-amplitude state-discrimination sweep preserved. (User chose "accept the loss".)
- **`LCH_qubit_spectroscopy_vs_ROamp`**: scqat's `AcStarkShiftAnalyzer` extracts f01
  per amplitude and fits shift vs amp²; it does **not** port qcat's full cavity-model
  fit (the `kc/ki/g/X_eff/f_bare` `given_factors` predicting wiring attenuation /
  target photon number). Pass `chi_eff=...` to `analyze()` to recover photon-number
  conversion once the units are confirmed.
- **`LCH_Ramsey`**: scqat auto-detects single vs beat (FFT-peak based) and omits
  `a_2` for the single model; `update_state` now reads `a_2` via `.get(..., 0.0)`.
  Model-selection on borderline data may differ from qcat's criterion.

## Validation status — IMPORTANT
- ✅ All scqat symbols used by the nodes import cleanly (verified in `LCHQM`).
- ⚠️ The analysis runs **lazily at plot time**, so import smoke-tests do **not**
  prove correctness. Each Tier-2 node should be validated against real data (or a
  saved `ds_raw` via `load_data_id`) — especially the dataset-contract assumptions
  (coord names/units) and the two reduced analyzers above.
- Full node import can't be smoke-tested end-to-end in either env right now:
  `LCHQM` has scqat but old qualibrate (no `qualibrate.core`); `LCHQM_test` has new
  qualibrate but scqat isn't installed yet. Installing scqat in `LCHQM_test` closes this.

## Remaining qcat references
Only in `calibrations/exclude/` (not loaded by qualibrate) and in two explanatory
code comments noting what was not ported. No active qcat **imports** remain.
