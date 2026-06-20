"""Time-dependent readout-resonator photon acquisition probe: vendor code only
(qm/quam/qualang_tools) - no qualibrate, no scqo, no scqat.

AC-Stark / photon-number-vs-time measurement. A readout-resonator test pulse
populates the resonator; the qubit is then probed by a saturation/x180 pulse at a
swept delay after the test pulse, while the drive frequency is swept across the
qubit line. Locating the AC-Stark-shifted qubit line per delay traces the
resonator photon number filling up and ringing down in time.

The sweep is `detuning` x `delay_time`; the delay is stepped in clock cycles
(4 ns granularity). Both qubits are read out as raw I/Q (state discrimination saves
the discriminated state instead). Downstream this is fit by scqat's
`ReadoutPulsePhotonEstimator`, which expects the `detuning` and `delay_time` coords.
"""

from typing import Callable, Optional

import numpy as np
import xarray as xr
from qm.qua import *

from qualang_tools.loops import from_array
from qualang_tools.units import unit

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    dfs,
    delay_time_array,
    num_shots: int,
    reset_type: str,
    xy_operation: str,
    xy_operation_amplitude_factor: float,
    xy_operation_len_in_ns: Optional[int],
    ro_operation: str,
    test_operation: str,
    rr_depletion_time: Optional[int],
    use_state_discrimination: bool,
    multiplexed: bool,
    simulate: bool = False,
):
    """Build the time-dependent readout-resonator photon QUA program.

    Returns ``(program, sweep_axes)``.

    `dfs` is the qubit detuning sweep in Hz; `delay_time_array` is the XY-probe
    delay sweep in ns (multiples of 4 ns); `qubits` is a BatchableList (see
    `_lib.select_qubits`). The delay is looped in clock cycles derived internally
    as ``delay_time_array // 4``.
    """
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)

    delay_tick_array = (np.asarray(delay_time_array) // 4).astype(int)

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "qubit frequency", "units": "Hz"}),
        "delay_time": xr.DataArray(delay_time_array, attrs={"long_name": "delay time", "units": "ns"}),
    }

    with program() as prog:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        df = declare(int)  # QUA variable for the qubit frequency
        delay_tick = declare(int)  # QUA variable for the XY-probe delay (in clock cycles)
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
                with for_(*from_array(df, dfs)):
                    with for_(*from_array(delay_tick, delay_tick_array)):
                        # Qubit initialization
                        for i, qubit in multiplexed_qubits.items():
                            # Update the qubit frequency
                            qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                            # Wait for the qubits to decay to the ground state
                            qubit.reset(reset_type, simulate)
                            # Flux sweeping for a qubit

                            xy_duration = (
                                xy_operation_len_in_ns * u.ns
                                if xy_operation_len_in_ns is not None
                                else qubit.xy.operations[xy_operation].length * u.ns
                            )

                        align()

                        # Qubit manipulation
                        # Bring the qubit to the desired point during the saturation pulse

                        for i, qubit in multiplexed_qubits.items():
                            # Apply saturation pulse to all qubits

                            wait((xy_duration * 5 + 16) // 4, qubit.resonator.name)
                            qubit.resonator.play(test_operation)
                            wait(delay_tick + 4, qubit.xy.name)
                            qubit.xy.play(xy_operation, duration=xy_duration // 4, amplitude_scale=xy_operation_amplitude_factor)

                            if rr_depletion_time is not None:
                                wait(rr_depletion_time * u.ns // 4, qubit.resonator.name)
                            else:
                                wait(qubit.resonator.depletion_time * u.ns // 4, qubit.resonator.name)
                        align()

                        # Measure the state of the resonators
                        for i, qubit in multiplexed_qubits.items():
                            if use_state_discrimination:
                                qubit.readout_state(state[i])
                                save(state[i], state_st[i])
                            else:
                                qubit.resonator.measure(ro_operation, qua_vars=(I[i], Q[i]))
                                # save data
                                save(I[i], I_st[i])
                                save(Q[i], Q_st[i])

            # Measure sequentially
            if not multiplexed:
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                if use_state_discrimination:
                    state_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"Q{i + 1}")

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
