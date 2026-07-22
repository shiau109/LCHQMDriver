"""QM backend: maps the scqo abstractions onto the QUAM device + the LCHQM probes.

The QM stack (qm/quam) and the probe helpers are imported lazily (inside methods)
so that `import customized.scqo.backend` works without an instrument and pulls in
qualang_tools only when data is actually acquired. This module is never imported by
the qualibrate calibration nodes - it is the optional scqo integration.

Neutral-name mapping: declared ONCE in ``customized/scqo/fieldmap.py`` (the
catalog ``scqo state --fields`` renders; drift-tested against scqo's per-category
pushed_fields). The executable conversions are ``QMReadableTransmon``'s
properties below (via customized.quam_fields, shared with the qualibrate
writebacks).
"""

from __future__ import annotations

import math
import warnings
from typing import TYPE_CHECKING, Any

import xarray as xr
from scqo.backend import Backend
from scqo.device import ComponentInfo, DeviceModel, make_view_base
from scqo.fieldmap import Unrealized, VendorBinding, VendorOnly

from customized import quam_fields
from customized.scqo.fieldmap import FIELD_BINDINGS, UNREALIZED, VENDOR_ONLY

#: MW-FEM full-scale grid (dBm): -11..+16 in 3 dB steps (power_tools validates the
#: same values; its docstring's "[-41,10]" range is stale).
_FS_GRID_MIN, _FS_GRID_MAX, _FS_GRID_STEP = -11, 16, 3
#: The canonical digital operating point: keep the pulse amplitude <= 0.5 full scale
#: (shared by the readout AND drive chain solves).
_CANONICAL_MAX_AMP = 0.5


def _solve_full_scale(name: str, target: float) -> int:
    """Bidirectional full-scale selection for an absolute port power: the SMALLEST
    grid value that keeps the amplitude <= 0.5 (it lands in (0.354, 0.5]). Chosen
    here — not by the bare power_tools helper, whose internal loop only ever bumps
    full-scale UP and would leave a tiny amplitude after a high-power era."""
    headroom = 20.0 * math.log10(2.0)  # amp 0.5 -> -6.02 dB below full scale
    fs = _FS_GRID_MIN + _FS_GRID_STEP * math.ceil(
        (target + headroom - _FS_GRID_MIN) / _FS_GRID_STEP
    )
    fs = min(_FS_GRID_MAX, max(_FS_GRID_MIN, fs))
    amp_needed = 10.0 ** ((target - fs) / 20.0)
    if amp_needed > _CANONICAL_MAX_AMP:  # only when fs is pinned at the grid top
        warnings.warn(
            f"{name}: hitting {target} dBm at full scale {fs} dBm needs "
            f"amplitude {amp_needed:.3f} > {_CANONICAL_MAX_AMP} — above the "
            f"canonical operating point"
        )
    return int(fs)

if TYPE_CHECKING:
    from scqo.experiment import Experiment


class QMReadableTransmon(make_view_base("ReadableTransmon")):
    """The scqo ReadableTransmon view backed by a QUAM qubit object.

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
    def drag_beta(self) -> float:
        return quam_fields.get_drag_beta(self._q)

    @drag_beta.setter
    def drag_beta(self, value: float) -> None:
        quam_fields.set_drag_beta(self._q, value)

    @property
    def readout_amp(self) -> float:
        return quam_fields.get_readout_amp(self._q)

    @readout_amp.setter
    def readout_amp(self, value: float) -> None:
        quam_fields.set_readout_amp(self._q, value)

    @property
    def readout_duration_s(self) -> float:
        return quam_fields.get_readout_duration(self._q)

    @readout_duration_s.setter
    def readout_duration_s(self, value: float) -> None:
        quam_fields.set_readout_duration(self._q, value)

    @property
    def readout_integration_s(self) -> float:
        return quam_fields.get_readout_integration(self._q)

    @readout_integration_s.setter
    def readout_integration_s(self, value: float) -> None:
        quam_fields.set_readout_integration(self._q, value)

    # readout_power_dbm / drive_power_dbm live HERE (not in quam_fields): the chain
    # solve needs quam_builder.tools.power_tools, whose module top imports quam —
    # quam_fields is contractually pure (stub-testable without an instrument).
    # backend.py already owns the lazy-vendor-import pattern, so the import stays
    # inside the accessors.
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
        # max_amplitude=1: the explicit full_scale_power_dbm already encodes the
        # <=0.5 policy; the helper then just sets fs + the exact amplitude.
        set_output_power_mw_channel(
            self._q.resonator, target, quam_fields.READOUT_OPERATION,
            full_scale_power_dbm=_solve_full_scale(self.name, target), max_amplitude=1,
        )

    # The drive twin, anchored to the SATURATION (spec) operation. The xy
    # full_scale_power_dbm is PORT-level and shared by every xy operation:
    # while it is off its standing value the stored pi_amp means a different
    # power (qubit_spectroscopy's run() sets and exactly reverts it; the
    # discrete grid + verbatim amplitude restore make the revert lossless).
    @property
    def drive_amp(self) -> float:
        return quam_fields.get_saturation_amp(self._q)

    @drive_amp.setter
    def drive_amp(self, value: float) -> None:
        quam_fields.set_saturation_amp(self._q, value)

    @property
    def drive_power_dbm(self) -> float:
        from quam_builder.tools.power_tools import get_output_power_mw_channel

        amp = self._q.xy.operations[quam_fields.SATURATION_OPERATION].amplitude
        if not amp:  # None or 0 -> log10 domain error / -inf must never reach the config
            raise ValueError(
                f"{self.name}: saturation amplitude is unset/zero — absolute power undefined"
            )
        return float(get_output_power_mw_channel(self._q.xy, quam_fields.SATURATION_OPERATION))

    @drive_power_dbm.setter
    def drive_power_dbm(self, value: float) -> None:
        from quam_builder.tools.power_tools import set_output_power_mw_channel

        target = float(value)
        set_output_power_mw_channel(
            self._q.xy, target, quam_fields.SATURATION_OPERATION,
            full_scale_power_dbm=_solve_full_scale(self.name, target), max_amplitude=1,
        )

    # idle_flux_v: the z-line offset SELECTED by z.flux_point (which named point
    # is active stays vendor config). Fixed-frequency qubits have no z — the
    # AttributeError surfaces as "unset" through _read_or_none / seeding, and a
    # roster that declares flux_bias on such a chip is a roster error anyway.
    @property
    def idle_flux_v(self) -> float:
        return quam_fields.get_idle_flux(self._q)

    @idle_flux_v.setter
    def idle_flux_v(self, value: float) -> None:
        quam_fields.set_idle_flux(self._q, value)


class QMTransmonPair(make_view_base("TransmonPair")):
    """The scqo TransmonPair view backed by a QUAM qubit-pair object (QCQ
    architecture): the coupler's standing offsets are the pair's knobs."""

    def __init__(self, pair: Any) -> None:
        self.name = pair.name if isinstance(getattr(pair, "name", None), str) else str(pair.id)
        self._qp = pair

    @property
    def coupler_decouple_v(self) -> float:
        return float(self._qp.coupler.decouple_offset)

    @coupler_decouple_v.setter
    def coupler_decouple_v(self, value: float) -> None:
        self._qp.coupler.decouple_offset = float(value)

    @property
    def coupler_interaction_v(self) -> float:
        return float(self._qp.coupler.interaction_offset)

    @coupler_interaction_v.setter
    def coupler_interaction_v(self, value: float) -> None:
        self._qp.coupler.interaction_offset = float(value)


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

    def component(self, name: str) -> "QMReadableTransmon | QMTransmonPair":
        if name in self._machine.qubits:
            return QMReadableTransmon(self._machine.qubits[name])
        pairs = getattr(self._machine, "qubit_pairs", {}) or {}
        if name in pairs:
            return QMTransmonPair(pairs[name])
        raise KeyError(name)

    def components(self) -> dict[str, ComponentInfo]:
        # Derived inventory (doctor's witness): every QUAM qubit is a
        # ReadableTransmon; every QUAM qubit_pair a TransmonPair whose derived
        # operations are the coupler line + its declared gate macros.
        out = {
            name: ComponentInfo("ReadableTransmon", operations=("rx", "readout"))
            for name in self._machine.qubits
        }
        for name, qp in (getattr(self._machine, "qubit_pairs", {}) or {}).items():
            macros = tuple(getattr(qp, "macros", {}) or {})
            out[name] = ComponentInfo("TransmonPair",
                                      operations=("coupler_bias", *macros))
        return out

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
            view = self.component(name)
            state[name] = {
                field: _read_or_none(view, field)
                for field in ("readout_freq", "drive_freq", "pi_amp", "drag_beta",
                              "drive_amp", "drive_power_dbm",
                              "readout_amp", "readout_power_dbm", "readout_duration_s",
                              "readout_integration_s", "idle_flux_v")
            }
        for name in (getattr(self._machine, "qubit_pairs", {}) or {}):
            view = self.component(name)
            state[name] = {
                field: _read_or_none(view, field)
                for field in ("coupler_decouple_v", "coupler_interaction_v")
            }
        return state


def _read_or_none(view: QMReadableTransmon, field: str) -> float | None:
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

    def field_bindings(self) -> dict[str, dict[str, VendorBinding]]:
        """The declared per-category neutral-field catalog (customized.scqo.fieldmap)
        — the conversion CODE is QMReadableTransmon/QMTransmonPair above; this is
        its description."""
        return {cat: dict(fields) for cat, fields in FIELD_BINDINGS.items()}

    def unrealized(self) -> dict[str, dict[str, Unrealized]]:
        """Pushed fields this backend declares it cannot realize (see fieldmap)."""
        return {cat: dict(fields) for cat, fields in UNREALIZED.items()}

    def vendor_only(self) -> dict[str, VendorOnly]:
        """QM-unique calibration knobs, vendor-owned (see fieldmap)."""
        return dict(VENDOR_ONLY)

    def power_context(self, qubits: list[str]) -> dict:
        """Raw readout + drive chain values per qubit (run-record provenance only)."""
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
                # The readout LO the data was taken at (QUAM resolves LO_frequency
                # to the port's upconverter_frequency): a hand-edited LO is
                # otherwise invisible in provenance. Only when the channel has one
                # (an LF-FEM resonator does not).
                lo = getattr(q.resonator, "LO_frequency", None)
                if lo is not None:
                    out[name]["readout_lo_freq_hz"] = float(lo)
            except Exception:  # provenance must never fail a run
                out[name] = {}
            # The drive chain behind drive_power_dbm — same never-fail rule, and
            # independent of the readout block (a qubit without a saturation op
            # still reports its readout chain).
            try:
                q = self._machine.qubits[name]
                sat = q.xy.operations[quam_fields.SATURATION_OPERATION]
                out[name].update({
                    "drive_full_scale_power_dbm": q.xy.opx_output.full_scale_power_dbm,
                    "saturation_amp": float(sat.amplitude),
                    "drive_power_dbm": float(
                        get_output_power_mw_channel(q.xy, quam_fields.SATURATION_OPERATION)
                    ),
                })
                lo = getattr(q.xy, "LO_frequency", None)
                if lo is not None:
                    out[name]["drive_lo_freq_hz"] = float(lo)
            except Exception:  # provenance must never fail a run
                pass
        return out

    def acquire(self, experiment: "Experiment") -> xr.Dataset:
        from customized.probes._lib import acquire as run_acquire

        # Progress denominator: per-shot experiments (single_shot_readout) declare
        # `num_shots` instead of the averaging mixin's `num_averages`.
        params = experiment.params
        shots = getattr(params, "num_averages", None) or getattr(params, "num_shots", 1)
        # A probe returns ONE of three shapes:
        #  - a ready-made xr.Dataset (drag_equator acquires itself with a baked config);
        #  - (program, sweep_axes, probe_module): the module's own acquire() fetches
        #    (tomography builds a heterogeneous-dims dataset per-shot);
        #  - (program, sweep_axes): the shared _lib.acquire fetches (the common path).
        res = experiment.probe()
        if isinstance(res, xr.Dataset):
            raw = res
        else:
            if isinstance(res, tuple) and len(res) == 3:
                program, sweep_axes, probe_module = res
                acquire_fn = getattr(probe_module, "acquire", run_acquire)
            else:
                program, sweep_axes = res
                acquire_fn = run_acquire
            raw = acquire_fn(
                self._machine, program, sweep_axes,
                num_shots=shots, timeout=self._timeout,
            )
        # Optional per-experiment raw reduction (e.g. joint two-qubit state
        # populations -> the pair experiment's canonical `signal` variable),
        # applied BEFORE canonicalization so the contract sees final variables.
        reduce = getattr(experiment, "reduce_raw", None)
        if reduce is not None:
            raw = reduce(raw)
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
           power_dbm)) — the fetcher preserves the probe's sweep_axes order, and the
           wrapper guarantees that order matches `define_sweep`; sizes are asserted
           per axis.

        On a structure mismatch the raw dataset is pickled for offline inspection —
        a bring-up run against the real QOP is never wasted (a raise here happens
        before the datastore ever sees the dataset).
        """
        # The raw target axis may be named per the probe family (single-qubit
        # probes: "qubit"; pair probes: "qubit_pair"); canonical is "target".
        raw_target = next((d for d in ("target", "qubit", "qubit_pair")
                           if d in raw.dims), None)
        if raw_target is None:
            raise ValueError(
                f"raw dataset has no target axis (expected one of "
                f"'qubit'/'qubit_pair'/'target'; dims={dict(raw.sizes)}, "
                f"data_vars={list(raw.data_vars)}); {_dump_raw(raw)}"
            )
        if raw_target != "target":
            raw = raw.rename({raw_target: "target"})
        # A probe that already emits a CONFORMING dataset passes straight through —
        # this is the path for probes whose sweep-axis names already equal the
        # experiment's (tomography's heterogeneous non-standard dims, drag_equator's
        # pre-built dataset, and the ported single-qubit probes). Experiments whose
        # probe uses non-canonical axis names (e.g. "detuning" vs "detuning_hz") do
        # NOT conform here and fall through to the positional renamer below.
        try:
            experiment.Contract.validate(raw)
            return raw
        except Exception:
            pass
        target = list(experiment.sweep_axes.keys())
        # Axis order from an actual data variable (Dataset.dims is unordered).
        ref_var = "I" if "I" in raw.data_vars else next(iter(raw.data_vars))
        raw_axes = [d for d in raw[ref_var].dims if d != "target"]
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
