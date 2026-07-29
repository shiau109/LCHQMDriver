"""Shared helpers for probes. No qualibrate imports."""

from typing import Callable, List, Optional

import xarray as xr
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualibration_libs.core import BatchableList
from qualibration_libs.data import XarrayDataFetcher


def select_qubits(machine, names: Optional[List[str]] = None, *, multiplexed: bool = False) -> BatchableList:
    """Node-free replacement for `qualibration_libs.parameters.get_qubits(node)`.

    Selects qubits from the machine by name (or `machine.active_qubits` when
    `names` is None/empty) and wraps them in the same `BatchableList` the
    qualibrate helper produces, so probes can iterate `qubits.batch()` /
    `qubits.get_names()` identically in both shells.
    """
    if not names:
        qubits = machine.active_qubits
    else:
        qubits = [machine.qubits[q] for q in names]
    if multiplexed:
        batched_groups = [list(range(len(qubits)))]
    else:
        batched_groups = [[i] for i in range(len(qubits))]
    return BatchableList(qubits, batched_groups)


def select_qubit_pairs(machine, names: Optional[List[str]] = None, *,
                       multiplexed: bool = False) -> BatchableList:
    """Node-free replacement for `qualibration_libs.parameters.get_qubit_pairs(node)`:
    selects pairs from the machine by name (or `machine.active_qubit_pairs` when
    `names` is None/empty) and wraps them in the same `BatchableList`."""
    if not names:
        pairs = machine.active_qubit_pairs
    else:
        pairs = [machine.qubit_pairs[p] for p in names]
    if multiplexed:
        batched_groups = [list(range(len(pairs)))]
    else:
        batched_groups = [[i] for i in range(len(pairs))]
    return BatchableList(pairs, batched_groups)


#: OPX1000 LF-FEM full-scale output, per port OUTPUT MODE. A stored waveform
#: peak at or above its port's value is clipped/corrupted at runtime and the
#: SIMULATOR DOES NOT SHOW IT, so flux probes guard their op amplitudes against
#: it before building.
_FEM_FULL_SCALE_V = {"direct": 0.5, "amplified": 2.5}

#: what to assume when a channel exposes no port (a test stub, or a QUAM class
#: that does not carry opx_output): the CONSERVATIVE rail, so an unknown port
#: refuses early rather than silently permitting a clipped waveform.
_DEFAULT_FULL_SCALE_V = _FEM_FULL_SCALE_V["direct"]


def dac_rail_v(channel) -> float:
    """The full-scale output voltage of a flux channel's LF-FEM port.

    The rail is a property of the PORT, not a constant: an OPX1000 LF-FEM output
    in "direct" mode reaches +/-0.5 V, in "amplified" mode +/-2.5 V. Hardcoding
    0.5 refuses every legitimate amplified-mode flux config -- and the live
    chipA state runs all of its flux ports amplified at 1.25 V op amplitudes, so
    that is not a hypothetical.

    Unknown port or mode -> the conservative direct-mode rail.
    """
    mode = getattr(getattr(channel, "opx_output", None), "output_mode", None)
    return _FEM_FULL_SCALE_V.get(mode, _DEFAULT_FULL_SCALE_V)


def idle_offset_v(channel, flux_point: str) -> float:
    """The standing DC offset a given named flux point applies, in volts.

    Deliberately takes the point as an ARGUMENT rather than reading
    ``channel.flux_point``: a probe must validate the bias it is actually
    applying, and the line's declared point is only the same thing while the
    scqo factory guard holds (``quam_fields.flux_point_problems``). Reading the
    declaration here would re-create the very gap that guard exists to close.
    """
    if flux_point == "zero":
        return 0.0
    try:
        return float(getattr(channel, f"{flux_point}_offset"))
    except (AttributeError, TypeError) as exc:
        raise ValueError(
            f"flux_point={flux_point!r} selects no offset on this flux line "
            f"(expected a '{flux_point}_offset' attribute)") from exc


#: QUA's bound on a DYNAMIC amplitude_scale (`play("op" * amp(v))`): the fixed-point
#: multiplier is only defined on (-2, 2), so a volts->scale conversion that lands
#: outside it is a build-time error, not a clipped waveform.
_MAX_AMP_SCALE = 2.0

#: The flux `const` amplitude convention: HALF the port's rail. It is what makes
#: the whole rail reachable through amp() -- scale +/-2 then spans +/-rail exactly
#: -- and it holds on both live chips (5Q4C direct 0.5 -> 0.25, chipA amplified
#: 2.5 -> 1.25). Probes VALIDATE it rather than assume it, because the failure it
#: prevents is silent: a too-small const caps the reachable window with no error,
#: and a too-large one clips inside the DAC where the simulator shows nothing.
_CONST_AMP_RAIL_FRACTION = 0.5


def const_amp_reference(channel, *, name: str, operation: str = "const") -> float:
    """The stored amplitude a volts->``amplitude_scale`` conversion divides by.

    Validated against the ``rail/2`` convention, so a config that silently caps
    the reachable flux window is refused by name with the value to set.
    """
    op = getattr(channel, "operations", {}).get(operation)
    if op is None:
        raise ValueError(
            f"{name}: flux channel has no '{operation}' operation - a flux "
            f"PULSE sweep has no amplitude reference to scale against")
    amplitude = float(getattr(op, "amplitude", 0.0))
    if amplitude == 0.0:
        raise ValueError(
            f"{name}: '{operation}' amplitude is 0 V - it is the divisor of the "
            f"volts->amplitude_scale conversion and cannot be zero")

    rail = dac_rail_v(channel)
    expected = rail * _CONST_AMP_RAIL_FRACTION
    if abs(amplitude - expected) > 1e-6 * rail:
        raise ValueError(
            f"{name}: '{operation}' amplitude is {amplitude} V but the flux "
            f"convention is half the port's full scale, {expected} V "
            f"(rail {rail} V). Below it the sweep cannot reach the rail "
            f"(QUA caps amplitude_scale at +/-{_MAX_AMP_SCALE}); above it the "
            f"waveform clips inside the DAC and the simulator shows nothing. "
            f"Set z.operations['{operation}'].amplitude = {expected} in the "
            f"QUAM state.")
    return amplitude


def check_flux_pulse_window(channel, *, name: str, idle_v: float, amps_v) -> float:
    """Validate an idle-relative flux PULSE sweep; return the reference amplitude.

    ``amps_v`` are the swept values in VOLTS, measured from ``idle_v`` (the
    standing DC bias the pulse rides on). Three ways this goes wrong, all
    silent on hardware:

    1. the ``const`` amplitude breaks the convention -> ``const_amp_reference``;
    2. a requested excursion needs ``|amplitude_scale| >= 2``, which QUA cannot
       express;
    3. ``idle_v + excursion`` exceeds the rail. The DAC emits the SUM, so a
       window that is fine on its own can still clip once it rides on a
       standing bias -- and nothing else in this repo checks the sum.
    """
    reference = const_amp_reference(channel, name=name)
    rail = dac_rail_v(channel)

    peak = max(abs(float(v)) for v in amps_v)
    scale = peak / reference
    if scale >= _MAX_AMP_SCALE:
        raise ValueError(
            f"{name}: flux window peak {peak} V needs amplitude_scale "
            f"{scale:.3f}, outside QUA's +/-{_MAX_AMP_SCALE} range "
            f"(reference {reference} V). The reachable excursion is "
            f"+/-{_MAX_AMP_SCALE * reference} V.")

    lo, hi = min(float(v) for v in amps_v), max(float(v) for v in amps_v)
    total = max(abs(idle_v + hi), abs(idle_v + lo))
    if total > rail:
        raise ValueError(
            f"{name}: the flux window rides on the standing bias, and "
            f"{idle_v} V idle + the window [{lo}, {hi}] V reaches {total} V, "
            f"past the port's {rail} V full scale. The DAC would clip and the "
            f"SIMULATOR WOULD NOT SHOW IT. Narrow the window to "
            f"+/-{rail - abs(idle_v)} V or move the idle bias.")
    return reference


def acquire(
    machine,
    prog,
    sweep_axes,
    *,
    num_shots: int,
    timeout: float,
    log: Optional[Callable] = None,
    config: Optional[dict] = None,
) -> xr.Dataset:
    """Connect to the QOP, execute the program and fetch the raw xr.Dataset.

    The execute-and-fetch half is identical for every swept experiment, so all
    probes share this one implementation. `config` defaults to
    `machine.generate_config()`; pass an explicit config when the program needs a
    pre-built one (e.g. a baked config carrying baking ops the fresh config lacks).
    """
    qmm = machine.connect()
    config = config if config is not None else machine.generate_config()
    # Execute the QUA program only if the quantum machine is available (this is to avoid interrupting running jobs).
    with qm_session(qmm, config, timeout=timeout) as qm:
        job = qm.execute(prog)
        data_fetcher = XarrayDataFetcher(job, sweep_axes)
        for dataset in data_fetcher:
            progress_counter(
                data_fetcher.get("n", 0),
                num_shots,
                start_time=data_fetcher.t_start,
            )
        # Expose possible runtime errors. execution_report is a method on some QM
        # API versions and a property on others — tolerate both.
        if log:
            rep = getattr(job, "execution_report", None)
            if callable(rep):
                log(rep())
            elif rep is not None:
                log(rep)
    return dataset
