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

from typing import TYPE_CHECKING, Any

import xarray as xr
from scqo.backend import Backend
from scqo.device import DeviceModel, QubitView

from customized import quam_fields

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
                for field in ("readout_freq", "drive_freq", "pi_amp", "readout_amp")
            }
        return state


def _read_or_none(view: QubitView, field: str) -> float | None:
    """Read a neutral field, returning None if the underlying QUAM value is unset."""
    try:
        return getattr(view, field)
    except (TypeError, AttributeError, KeyError):
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
           power_db)) — the fetcher preserves the probe's sweep_axes order, and the
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
