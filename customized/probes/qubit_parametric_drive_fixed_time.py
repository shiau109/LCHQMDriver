"""Parametric-drive resonance-map (fixed time) acquisition probe: vendor code only (qm/quam) - no qualibrate, no scqo, no scqat.

Prepare the qubit (x180), apply a fixed-duration parametric (flux-line) drive while sweeping the drive
amplitude ratio and frequency, then read out the excited-state population. The resonance peak(s) on
the 2-D amplitude x frequency map are fitted downstream.
"""

from typing import Callable, Optional

import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.loops import from_array
from qualang_tools.units import unit

from customized.probes._lib import acquire as _acquire

# Largest magnitude QUA accepts for a dynamic `amplitude_scale` (the fixed-point range is (-2, 2)).
_MAX_AMP_SCALE = 2.0


def build_program(
    machine,
    qubits,
    *,
    r_amps,
    freqs,
    amp_mode: str,
    driving_time_in_ns: int,
    num_shots: int,
    reset_type: str,
    use_state_discrimination: bool,
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the parametric-drive (fixed-time) QUA program. Returns (program, sweep_axes).

    `r_amps` is the drive-amplitude sweep (volts if `amp_mode == "absolute"`, else a unitless
    prefactor); `freqs` is the drive-frequency sweep (Hz). `qubits` is a BatchableList
    (see `_lib.select_qubits`). Raises ValueError if the emitted `amplitude_scale` would leave
    QUA's (-2, 2) fixed-point range.
    """
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)

    # Validate the sweep stays within QUA's (-2, 2) amplitude_scale range. In "absolute" mode
    # the emitted scale is a/ref, so the bound depends on each qubit's z 'const' op amplitude.
    if amp_mode == "absolute":
        for qubit in qubits:
            ref = float(qubit.z.operations["const"].amplitude)
            max_scale = float(np.max(np.abs(r_amps))) / abs(ref)
            if max_scale >= _MAX_AMP_SCALE:
                raise ValueError(
                    f"Absolute amplitude sweep for {qubit.name} exceeds QUA's amplitude_scale range: "
                    f"max |a/ref| = {max_scale:.3f} >= {_MAX_AMP_SCALE} (ref = {ref} V). "
                    f"Reduce the amplitude range or use amp_mode='prefactor'."
                )
    else:  # prefactor
        max_scale = float(np.max(np.abs(r_amps)))
        if max_scale >= _MAX_AMP_SCALE:
            raise ValueError(
                f"Prefactor amplitude sweep exceeds QUA's amplitude_scale range: "
                f"max |a| = {max_scale:.3f} >= {_MAX_AMP_SCALE}."
            )

    amp_units = "V" if amp_mode == "absolute" else "arb."
    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "drive_amp": xr.DataArray(r_amps, attrs={"long_name": "drive amplitude", "units": amp_units}),
        "driving_frequency": xr.DataArray(freqs, attrs={"long_name": "driving frequency", "units": "Hz"}),
    }

    with program() as prog:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        ra = declare(float)  # QUA variable for the qubit frequency
        f_drive = declare(int)  # QUA variable for the qubit frequency
        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                with for_(*from_array(ra, r_amps)):
                    with for_(*from_array(f_drive, freqs)):

                        for i, qubit in multiplexed_qubits.items():
                            qubit.reset(reset_type, simulate, log_callable=log)
                            # Update the qubit frequency
                            qubit.z.update_frequency(f_drive)

                        for i, qubit in multiplexed_qubits.items():
                            # if i == 0:
                            qubit.xy.play("x180")
                        align()
                        wait(200 // 4)
                        for i, qubit in multiplexed_qubits.items():

                            if i == 0:
                                qubit.z.reset_if_phase()
                                ref = float(qubit.z.operations["const"].amplitude)
                                amp_scale = ra / ref if amp_mode == "absolute" else ra
                                qubit.z.play("const", amplitude_scale=amp_scale, duration=driving_time_in_ns * u.ns // 4)
                        align()

                        for i, qubit in multiplexed_qubits.items():
                            if use_state_discrimination:
                                qubit.readout_state(state[i])
                                save(state[i], state_st[i])
                            else:
                                qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                                save(I[i], I_st[i])
                                save(Q[i], Q_st[i])
                        align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                if use_state_discrimination:
                    state_st[i].buffer(len(freqs)).buffer(len(r_amps)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(freqs)).buffer(len(r_amps)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(freqs)).buffer(len(r_amps)).average().save(f"Q{i + 1}")

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
