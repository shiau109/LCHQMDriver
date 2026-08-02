"""Long-time (spectroscopy) cryoscope probe: vendor code only (qm/quam) — no qualibrate, no scqo.

Flux-line step response by qubit spectroscopy vs wait-time INTO a parked flux
pulse. Sequence per (detuning, wait): reset -> set the drive near the parked
qubit frequency (``df + IF + center_offset_hz``) -> play a long flux ``const``
pulse -> wait ``t`` into it -> play an ``x180`` spectroscopy pulse -> readout.
Per wait-time the spectroscopy peak center gives the qubit frequency, which maps
to the delivered flux; the flux settling is fit downstream to a sum of
exponentials. This reaches the microsecond tails the Ramsey cryoscope cannot.

PULSE CONTRACT: ``flux_amp_v`` is the parked flux amplitude in VOLTS measured
from the standing DC bias ``initialize_qpu`` applies — the z ``const`` rides on
that offset, so it is idle-relative. ``flux_point`` is passed EXPLICITLY because
the DAC emits ``idle + excursion`` and the number validated against the rail must
be the number that plays.

CENTER OFFSET: ``center_offset_hz`` is the arch-predicted parked detuning the
scqo experiment computes; the drive is shifted by it (NO LO shift — band-limited)
so the spectroscopy window stays centered on the peak. It is a plain frequency
shift added to ``update_frequency``.

Single qubit only: the sequence is built per qubit (one parked drive, one flux
line, one wait axis); run targets one at a time.
"""

from typing import Callable, Optional

import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.loops import from_array

from customized.probes._flux_limits import check_flux_pulse_relative, idle_offset_v
from customized.probes._lib import acquire as _acquire

#: extra flux-pulse cycles held past the spectroscopy pulse so the drive sits
#: fully inside the parked flux (4 ns cycles).
_FLUX_TAIL_CYCLES = 25


def validate_inputs(qubits, flux_amp_v: float, flux_point: str) -> float:
    """Pure pre-flight checks (no QUA); return the flux ``const`` reference amplitude.

    Refuses, by name and before any hardware time: more than one target (the
    sequence is built per qubit); a missing flux line; and a parked flux whose
    ``idle + flux_amp_v`` clips the port or needs an ``amplitude_scale`` QUA cannot
    express (:func:`check_flux_pulse_relative`).
    """
    if len(qubits) != 1:
        names = list(qubits.get_names())
        raise ValueError(
            f"qubit_spectroscopy_cryoscope builds its spectroscopy sequence per "
            f"qubit and supports one target at a time, got {len(qubits)}: {names}. "
            f"Run them one at a time.")
    qubit = qubits[0]
    z = getattr(qubit, "z", None)
    if z is None:
        raise ValueError(
            f"{qubit.name}: no flux line, but the spectroscopy cryoscope parks a z "
            f"pulse to detune the qubit — it cannot run on a qubit with no z channel.")
    return check_flux_pulse_relative(
        z, name=f"{qubit.name} spectroscopy cryoscope flux pulse",
        idle_v=idle_offset_v(z, flux_point), amps_v=[float(flux_amp_v)])


def build_program(
    machine,
    qubits,
    *,
    dfs,
    wait_cycles,
    flux_amp_v: float,
    center_offset_hz: float,
    num_shots: int,
    reset_type: str = "thermal",
    operation: str = "x180",
    operation_amp: float = 1.0,
    use_state_discrimination: bool = False,
    simulate: bool = False,
    flux_point: str = "joint",
    log: Optional[Callable] = None,
):
    """Build the long-time cryoscope QUA program. Returns ``(program, sweep_axes)``.

    ``dfs`` is the drive-detuning sweep (Hz), swept OUTER; ``wait_cycles`` the
    wait-into-the-flux sweep in clock cycles (4 ns), swept INNER (typically
    log-spaced). ``flux_amp_v`` is the idle-relative parked amplitude and
    ``center_offset_hz`` the arch-predicted parked detuning the drive is shifted
    by. No baking — a plain stretched ``const`` plus a fixed spectroscopy pulse —
    so the shared ``_lib.acquire`` fetches it (the adapter returns ``(prog, axes)``).
    """
    amp_ref = validate_inputs(qubits, flux_amp_v, flux_point)
    qubit = qubits[0]
    dfs = np.round(np.asarray(dfs)).astype(int)
    wait_cycles = np.unique(np.asarray(wait_cycles).astype(int))
    const_scale = float(flux_amp_v) / amp_ref
    offset_hz = int(round(float(center_offset_hz)))
    op_len_cycles = qubit.xy.operations[operation].length // 4

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning_hz": xr.DataArray(
            dfs.astype(float), attrs={"long_name": "drive detuning", "units": "Hz"}),
        "wait_time_ns": xr.DataArray(
            (4 * wait_cycles).astype(float),
            attrs={"long_name": "wait into the flux pulse", "units": "ns"}),
    }

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        df = declare(int)
        t = declare(int)
        if use_state_discrimination:
            state = declare(int)
            state_st = declare_stream()

        machine.initialize_qpu(target=qubit, flux_point=flux_point)
        align()

        with for_(n, 0, n < num_shots, n + 1):
            save(n, n_st)
            with for_(*from_array(df, dfs)):
                with for_each_(t, wait_cycles):
                    qubit.reset(reset_type, simulate, log_callable=log)
                    # park the drive at the arch-predicted detuned frequency + the swept df
                    qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency + offset_hz)
                    align()
                    # hold the flux on while the drive waits t into it, then probes
                    qubit.z.play("const", amplitude_scale=const_scale,
                                 duration=t + op_len_cycles + _FLUX_TAIL_CYCLES)
                    qubit.xy.wait(t)
                    qubit.xy.play(operation, amplitude_scale=operation_amp)
                    align()
                    if use_state_discrimination:
                        qubit.readout_state(state)
                        save(state, state_st)
                    else:
                        qubit.resonator.measure("readout", qua_vars=(I[0], Q[0]))
                        save(I[0], I_st[0])
                        save(Q[0], Q_st[0])

        with stream_processing():
            n_st.save("n")
            if use_state_discrimination:
                state_st.buffer(len(wait_cycles)).buffer(len(dfs)).average().save("state1")
            else:
                I_st[0].buffer(len(wait_cycles)).buffer(len(dfs)).average().save("I1")
                Q_st[0].buffer(len(wait_cycles)).buffer(len(dfs)).average().save("Q1")

    return prog, sweep_axes


def acquire(
    machine,
    prog,
    sweep_axes,
    *,
    num_shots: int,
    timeout: float,
    log: Optional[Callable] = None,
) -> xr.Dataset:
    """Connect to the QOP, execute the program and fetch the raw xr.Dataset."""
    return _acquire(machine, prog, sweep_axes, num_shots=num_shots, timeout=timeout, log=log)
