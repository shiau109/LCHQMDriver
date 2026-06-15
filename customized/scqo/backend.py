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

if TYPE_CHECKING:
    from scqo.experiment import Experiment

#: The operation whose amplitude is the calibrated pi pulse (the neutral pi_amp).
PI_OPERATION = "x180"


class QMQubitView(QubitView):
    """A scqo QubitView backed by a QUAM qubit object."""

    def __init__(self, qubit: Any) -> None:
        self.name = qubit.name
        self._q = qubit

    @property
    def readout_freq(self) -> float:
        return float(self._q.resonator.RF_frequency)

    @readout_freq.setter
    def readout_freq(self, value: float) -> None:
        self._q.resonator.RF_frequency = float(value)

    @property
    def drive_freq(self) -> float:
        return float(self._q.f_01)

    @drive_freq.setter
    def drive_freq(self, value: float) -> None:
        # Move f_01 to the requested absolute value and shift the xy drive RF by the
        # same delta, preserving any fixed f_01 <-> RF offset (matches the LCHQM
        # Ramsey writeback, which subtracts one detuning delta from both).
        delta = float(value) - float(self._q.f_01)
        self._q.f_01 = float(value)
        self._q.xy.RF_frequency = float(self._q.xy.RF_frequency) + delta

    @property
    def pi_amp(self) -> float:
        return float(self._q.xy.operations[PI_OPERATION].amplitude)

    @pi_amp.setter
    def pi_amp(self, value: float) -> None:
        self._q.xy.operations[PI_OPERATION].amplitude = float(value)


class QMDeviceModel(DeviceModel):
    """Wraps a QUAM machine (`Quam`)."""

    def __init__(self, machine: Any) -> None:
        self._machine = machine

    def qubit(self, name: str) -> QMQubitView:
        return QMQubitView(self._machine.qubits[name])

    def save(self) -> None:
        self._machine.save()

    def snapshot(self) -> dict:
        # Loop memory: report every qubit's state, tolerating uncalibrated qubits
        # (an unset QUAM field such as f_01=None yields None rather than crashing).
        state: dict[str, dict] = {}
        for name in self._machine.qubits:
            view = self.qubit(name)
            state[name] = {field: _read_or_none(view, field) for field in ("readout_freq", "drive_freq", "pi_amp")}
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
        raw = run_acquire(
            self._machine,
            program,
            sweep_axes,
            num_shots=experiment.params.num_averages,  # type: ignore[attr-defined]
            timeout=self._timeout,
        )
        return self._to_canonical(raw, experiment)

    @staticmethod
    def _to_canonical(raw: xr.Dataset, experiment: "Experiment") -> xr.Dataset:
        """Relabel the raw probe dataset into scqo's convention: dims (qubit, <sweep>),
        vars I/Q. The probe already emits I/Q with a qubit dim; only the sweep axis is
        renamed to the scqo `define_sweep` name (e.g. idle_time -> idle_time_ns,
        amp_prefactor -> amp_factor).
        """
        non_qubit_dims = [d for d in raw.dims if d != "qubit"]
        target = list(experiment.sweep_axes.keys())
        if len(non_qubit_dims) == 1 and len(target) == 1:
            if non_qubit_dims[0] != target[0]:
                raw = raw.rename({non_qubit_dims[0]: target[0]})
            return raw
        raise NotImplementedError(
            "Multi-axis canonical relabeling is not implemented yet (only single-sweep "
            f"experiments). Raw sweep dims={non_qubit_dims}, scqo axes={target}."
        )
