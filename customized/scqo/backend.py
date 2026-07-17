"""QM backend: maps the scqo abstractions onto the QUAM device + the LCHQM probes.

The QM stack (qm/quam) and the probe helpers are imported lazily (inside methods)
so that `import customized.scqo.backend` works without an instrument and pulls in
qualang_tools only when data is actually acquired. This module is never imported by
the qualibrate calibration nodes - it is the optional scqo integration.

Neutral-name mapping (scqo QubitView -> QUAM qubit), confirmed by the LCHQM update
modules in customized/node/LCH_*/update.py:
    readout_freq  <-> q.resonator.RF_frequency
    drive_freq    <-> q.f_01  (and q.xy.RF_frequency, shifted by the same delta)
    pi_amp        <-> q.xy.operations['x180'].amplitude
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any

import xarray as xr
from scqo.backend import Backend
from scqo.device import DeviceModel, QubitView

from customized import quam_fields

#: MW-FEM full-scale grid (dBm): -11..+16 in 3 dB steps (power_tools validates the
#: same values; its docstring's "[-41,10]" range is stale).
_FS_GRID_MIN, _FS_GRID_MAX, _FS_GRID_STEP = -11, 16, 3
#: The canonical digital operating point: keep the readout amplitude <= 0.5 full scale.
_CANONICAL_MAX_AMP = 0.5

if TYPE_CHECKING:
    from scqo.experiment import Experiment


class QMQubitView(QubitView):
    """A scqo QubitView backed by a QUAM qubit object.

    The neutral field <-> QUAM mapping lives in :mod:`customized.quam_fields`, shared with
    the qualibrate ``apply_update`` writebacks, so it is defined exactly once.
    """

    def __init__(self, qubit: Any) -> None:
        self.name = qubit.name
        self._q = qubit

    @property
    def readout_freq(self) -> float:
        return quam_fields.get_readout_freq(self._q)

    @readout_freq.setter
    def readout_freq(self, value: float) -> None:
        quam_fields.set_readout_freq(self._q, value)

    @property
    def drive_freq(self) -> float:
        return quam_fields.get_drive_freq(self._q)

    @drive_freq.setter
    def drive_freq(self, value: float) -> None:
        quam_fields.set_drive_freq(self._q, value)

    @property
    def pi_amp(self) -> float:
        return quam_fields.get_pi_amp(self._q)

    @pi_amp.setter
    def pi_amp(self, value: float) -> None:
        quam_fields.set_pi_amp(self._q, value)

    @property
    def readout_amp(self) -> float:
        return quam_fields.get_readout_amp(self._q)

    @readout_amp.setter
    def readout_amp(self, value: float) -> None:
        quam_fields.set_readout_amp(self._q, value)

    # readout_power_dbm lives HERE (not in quam_fields): the chain solve needs
    # quam_builder.tools.power_tools, whose module top imports quam — quam_fields is
    # contractually pure (stub-testable without an instrument). backend.py already
    # owns the lazy-vendor-import pattern, so the import stays inside the accessors.
    @property
    def readout_power_dbm(self) -> float:
        from quam_builder.tools.power_tools import get_output_power_mw_channel

        amp = self._q.resonator.operations[quam_fields.READOUT_OPERATION].amplitude
        if not amp:  # None or 0 -> log10 domain error / -inf must never reach the config
            raise ValueError(
                f"{self.name}: readout amplitude is unset/zero — absolute power undefined"
            )
        return float(get_output_power_mw_channel(self._q.resonator, quam_fields.READOUT_OPERATION))

    @readout_power_dbm.setter
    def readout_power_dbm(self, value: float) -> None:
        from quam_builder.tools.power_tools import set_output_power_mw_channel

        target = float(value)
        # Bidirectional full-scale selection: the SMALLEST grid value that keeps the
        # amplitude <= 0.5 (it lands in (0.354, 0.5]). Chosen here — not by the bare
        # helper, whose internal loop only ever bumps full-scale UP and would leave a
        # tiny amplitude after a high-power era.
        headroom = 20.0 * math.log10(2.0)  # amp 0.5 -> -6.02 dB below full scale
        fs = _FS_GRID_MIN + _FS_GRID_STEP * math.ceil(
            (target + headroom - _FS_GRID_MIN) / _FS_GRID_STEP
        )
        fs = min(_FS_GRID_MAX, max(_FS_GRID_MIN, fs))
        amp_needed = 10.0 ** ((target - fs) / 20.0)
        if amp_needed > _CANONICAL_MAX_AMP:  # only when fs is pinned at the grid top
            warnings.warn(
                f"{self.name}: hitting {target} dBm at full scale {fs} dBm needs "
                f"amplitude {amp_needed:.3f} > {_CANONICAL_MAX_AMP} — above the "
                f"canonical operating point"
            )
        # max_amplitude=1: the explicit full_scale_power_dbm already encodes the
        # <=0.5 policy; the helper then just sets fs + the exact amplitude.
        set_output_power_mw_channel(
            self._q.resonator, target, quam_fields.READOUT_OPERATION,
            full_scale_power_dbm=int(fs), max_amplitude=1,
        )


class QMDeviceModel(DeviceModel):
    """Wraps a QUAM machine (`Quam`).

    ``state_dir``: explicit save target. Set it whenever the machine was loaded from a
    non-default location (e.g. the setup's ``instrument_config`` folder) — a bare
    ``machine.save()`` writes to QUAM's configured default (the live ``quam_state/``),
    which may not be the folder this session's state actually lives in.
    """

    def __init__(self, machine: Any, state_dir: str | None = None) -> None:
        self._machine = machine
        self._state_dir = state_dir

    def qubit(self, name: str) -> QMQubitView:
        return QMQubitView(self._machine.qubits[name])

    def save(self) -> None:
        if self._state_dir is not None:
            self._machine.save(path=self._state_dir)
        else:
            self._machine.save()

    def snapshot(self) -> dict:
        # Loop memory: report every qubit's state, tolerating uncalibrated qubits
        # (an unset QUAM field such as f_01=None yields None rather than crashing).
        state: dict[str, dict] = {}
        for name in self._machine.qubits:
            view = self.qubit(name)
            state[name] = {
                field: _read_or_none(view, field)
                for field in ("readout_freq", "drive_freq", "pi_amp", "readout_amp",
                              "readout_power_dbm")
            }
        return state


def _read_or_none(view: QubitView, field: str) -> float | None:
    """Read a neutral field, returning None if the underlying QUAM value is unset.

    ValueError covers readout_power_dbm on a zero/unset readout amplitude (the
    absolute power is undefined there, not zero)."""
    try:
        return getattr(view, field)
    except (TypeError, AttributeError, KeyError, ValueError):
        return None


class QMBackend(Backend):
    """scqo Backend over a Quantum Machines OPX (via QUAM + the LCHQM probes)."""

    def __init__(self, machine: Any, *, timeout: float = 120) -> None:
        self._machine = machine
        self._device = QMDeviceModel(machine)
        self._timeout = timeout

    @classmethod
    def load(cls, *, state_path: str | None = None, timeout: float = 120) -> "QMBackend":
        """Construct from a QUAM state. ``state_path`` overrides ``QUAM_STATE_PATH``;
        when omitted the env / default configuration is used."""
        import os

        from quam_config import Quam

        if state_path is not None:
            os.environ["QUAM_STATE_PATH"] = state_path
        return cls(Quam.load(), timeout=timeout)

    @property
    def device(self) -> QMDeviceModel:
        return self._device

    @property
    def machine(self) -> Any:
        """The underlying QUAM machine (read by the QM experiment probes)."""
        return self._machine

    def power_context(self, qubits: list[str]) -> dict:
        """Raw readout output-chain values per qubit (run-record provenance only)."""
        from quam_builder.tools.power_tools import get_output_power_mw_channel

        out: dict = {}
        for name in qubits:
            try:
                q = self._machine.qubits[name]
                ro = q.resonator.operations[quam_fields.READOUT_OPERATION]
                out[name] = {
                    "full_scale_power_dbm": q.resonator.opx_output.full_scale_power_dbm,
                    "readout_amplitude": float(ro.amplitude),
                    "readout_power_dbm": float(
                        get_output_power_mw_channel(q.resonator, quam_fields.READOUT_OPERATION)
                    ),
                }
            except Exception:  # provenance must never fail a run
                out[name] = {}
        return out

    def acquire(self, experiment: "Experiment") -> xr.Dataset:
        from customized.probes._lib import acquire as run_acquire

        program, sweep_axes = experiment.probe()  # QM probe returns (program, sweep_axes)
        # Progress denominator: per-shot experiments (single_shot_readout) declare
        # `num_shots` instead of the averaging mixin's `num_averages`.
        params = experiment.params
        shots = getattr(params, "num_averages", None) or getattr(params, "num_shots", 1)
        raw = run_acquire(
            self._machine,
            program,
            sweep_axes,
            num_shots=shots,
            timeout=self._timeout,
        )
        return self._to_canonical(raw, experiment)

    @staticmethod
    def _to_canonical(raw: xr.Dataset, experiment: "Experiment") -> xr.Dataset:
        import numpy as np
        
        if experiment.name == "qubit_tomography":
            from calibration_utils.new_tomography.analysis import process_raw_dataset
            class MockQubits:
                def __init__(self, qubits):
                    self._q = qubits
                def get_names(self):
                    return self._q
            class MockNode:
                def __init__(self, exp):
                    self.parameters = exp.params
                    self.parameters.num_shots = exp.params.num_averages
                    self.namespace = {"qubits": MockQubits(exp.params.qubits)}
            return process_raw_dataset(raw, MockNode(experiment))

        if experiment.name == "qubit_sqrb":
            qubits = list(experiment.params.qubits)
            use_sd = bool(experiment.params.use_state_discrimination)
            i_rows = []
            q_rows = []
            
            for idx, name in enumerate(qubits):
                q_idx = idx + 1
                if use_sd:
                    key = f"state{q_idx}"
                    if key not in raw.data_vars:
                        raise KeyError(f"Acquisition variable {key!r} not found in raw data.")
                    val = 1.0 - np.asarray(raw[key].values)
                    val = val.T
                    i_rows.append(val)
                    q_rows.append(np.zeros_like(val))
                else:
                    key_i = f"I{q_idx}"
                    key_q = f"Q{q_idx}"
                    if key_i not in raw.data_vars or key_q not in raw.data_vars:
                        raise KeyError(f"Acquisition variables {key_i!r}/{key_q!r} not found in raw data.")
                    val_i = np.asarray(raw[key_i].values).T
                    val_q = np.asarray(raw[key_q].values).T
                    i_rows.append(val_i)
                    q_rows.append(val_q)
                    
            return xr.Dataset(
                {
                    "I": (("qubit", "depth", "sequence_idx"), np.stack(i_rows)),
                    "Q": (("qubit", "depth", "sequence_idx"), np.stack(q_rows)),
                },
                coords={
                    "qubit": qubits,
                    "depth": np.array(experiment.params.get_depths()),
                    "sequence_idx": np.arange(experiment.params.num_random_sequences)
                }
            )

        """Relabel the raw probe dataset into scqo's convention: dims (qubit, *sweeps),
        vars I/Q. The probe already emits I/Q with a qubit dim.

        Two mapping modes for the sweep axes:

        1. Name-based (preferred, order-independent): when the raw non-qubit dim
           NAMES already equal the scqo `define_sweep` names as a set, nothing is
           renamed — only per-name sizes are asserted. This is how probes whose raw
           nesting order differs from the scqo declaration order stay correct: the
           QUA stream nesting fixes the raw dim order (e.g. flux spectroscopy is
           (detuning, flux) on the wire while scqo declares (flux, detuning));
           downstream code transposes by NAME, so order does not matter, but a
           positional rename would silently swap equal-sized axes. Wrappers opt in
           by returning `sweep_axes` keyed with the canonical names in raw nesting
           order (readout_fidelity's probe already is canonical).

        2. Positional fallback: axes are renamed positionally to the scqo names
           (e.g. idle_time -> idle_time_ns, (detuning, power) -> (detuning_hz,
           power_dbm)) — the fetcher preserves the probe's sweep_axes order, and the
           wrapper guarantees that order matches `define_sweep`; sizes are asserted
           per axis.

        On a structure mismatch the raw dataset is pickled for offline inspection —
        a bring-up run against the real QOP is never wasted (a raise here happens
        before the datastore ever sees the dataset).
        """
        target = list(experiment.sweep_axes.keys())
        if "qubit" not in raw.dims:
            raise ValueError(
                f"raw dataset has no 'qubit' dimension (dims={dict(raw.sizes)}, "
                f"data_vars={list(raw.data_vars)}); {_dump_raw(raw)}"
            )
        # Axis order from an actual data variable (Dataset.dims is unordered).
        ref_var = "I" if "I" in raw.data_vars else next(iter(raw.data_vars))
        raw_axes = [d for d in raw[ref_var].dims if d != "qubit"]
        if len(raw_axes) != len(target):
            raise NotImplementedError(
                f"sweep-axis count mismatch: raw {raw_axes} vs scqo {target}, "
                f"data_vars={list(raw.data_vars)}; {_dump_raw(raw)}"
            )
        if set(raw_axes) == set(target):
            # Name-based: already canonical; assert sizes by name, never reorder.
            for name in target:
                if raw.sizes[name] != len(experiment.sweep_axes[name]):
                    raise ValueError(
                        f"axis size mismatch: raw {name}={raw.sizes[name]} vs "
                        f"scqo {name}={len(experiment.sweep_axes[name])}; {_dump_raw(raw)}"
                    )
            return raw
        for raw_dim, name in zip(raw_axes, target):
            if raw.sizes[raw_dim] != len(experiment.sweep_axes[name]):
                raise ValueError(
                    f"axis size mismatch: raw {raw_dim}={raw.sizes[raw_dim]} vs "
                    f"scqo {name}={len(experiment.sweep_axes[name])}; {_dump_raw(raw)}"
                )
        rename = {r: t for r, t in zip(raw_axes, target) if r != t}
        return raw.rename(rename) if rename else raw


def _dump_raw(raw: xr.Dataset) -> str:
    """Pickle the raw QOP dataset for offline inspection (bring-up diagnostics)."""
    import pickle
    import tempfile
    from datetime import datetime
    from pathlib import Path

    dump = Path(tempfile.gettempdir()) / f"qm_raw_{datetime.now():%Y%m%d-%H%M%S}.pkl"
    try:
        with open(dump, "wb") as f:
            pickle.dump(raw, f)
        return f"raw dataset pickled to {dump}"
    except Exception as err:
        return f"raw dataset could not be pickled ({type(err).__name__}: {err})"
