"""Instrument probes: the acquisition half of each experiment (params in -> Dataset out).

A probe is the only code in this repo shared between the two orchestrators: the
qualibrate shells in `calibrations/LCH_*.py` call it today, and the scqo
`QMBackend` (planned) will call exactly the same functions. Everything
qualibrate-specific (parameter schema, scqat analysis adapter, state-update
policy) lives in `customized/node/LCH_<name>/` instead.

Import rules for everything under this package:
- MAY import: qm.qua, quam, qualang_tools, qualibration_libs.core / .data
  (framework-free utilities), numpy, xarray.
- MUST NOT import: qualibrate, scqo, or scqat - probes acquire, they never fit.
- Functions take explicit data in (machine, qubits, plain kwargs) and return
  plain data out (program, xr.Dataset) - never a `node`.
"""
