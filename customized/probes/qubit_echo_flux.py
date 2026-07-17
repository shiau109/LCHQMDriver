"""Qubit Echo vs Flux (T2 Echo Spectrum) acquisition probe: vendor code only (qm/quam).

Excite with x90, wait and apply Z bias pulse, refocus with central x180, wait, final x90, then measure.
"""

from typing import Callable, Optional, List
import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.units import unit

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    num_shots: int,
    idle_times_cycles: List[int],
    flux_amp_array: List[float],
    use_state_discrimination: bool,
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the T2 echo vs flux QUA program. Returns (program, sweep_axes)."""
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)
    
    idle_times_cycles = np.unique(np.asarray(idle_times_cycles))
    flux_amp_array = np.asarray(flux_amp_array)

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "flux_amp": xr.DataArray(flux_amp_array, attrs={"long_name": "flux amplitude", "units": "V"}),
        "wait_time_ns": xr.DataArray(8 * idle_times_cycles, attrs={"long_name": "total echo wait time", "units": "ns"}),
    }

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        t = declare(int)
        dc = declare(fixed)

        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        for multiplexed_qubits in qubits.batch():
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                with for_(*from_array(dc, flux_amp_array)):
                    with for_each_(t, idle_times_cycles):
                        # 1. Reset
                        for i_q, qubit in multiplexed_qubits.items():
                            qubit.reset("thermal", simulate, log_callable=log)
                        align()

                        # 2. Hahn echo sequence & Z pulse
                        for i_q, qubit in multiplexed_qubits.items():
                            qubit.align()
                            # Total dephasing wait duration is 2 * t + central pi pulse length
                            pi_len = qubit.xy.operations["x180"].length // 4
                            qubit.z.play(
                                "const",
                                amplitude_scale=dc / qubit.z.operations["const"].amplitude,
                                duration=2 * t + pi_len,
                            )
                            # Echo gates
                            qubit.xy.play("x90")
                            qubit.xy.wait(t)
                            qubit.xy.play("x180")
                            qubit.xy.wait(t)
                            qubit.xy.play("x90")
                            qubit.align()

                        # 3. Measurement
                        for i_q, qubit in multiplexed_qubits.items():
                            if use_state_discrimination:
                                qubit.readout_state(state[i_q])
                                save(state[i_q], state_st[i_q])
                            else:
                                qubit.resonator.measure("readout", qua_vars=(I[i_q], Q[i_q]))
                                save(I[i_q], I_st[i_q])
                                save(Q[i_q], Q_st[i_q])
                        align()

        with stream_processing():
            n_st.save("n")
            for i_q in range(num_qubits):
                if use_state_discrimination:
                    state_st[i_q].buffer(len(idle_times_cycles)).buffer(len(flux_amp_array)).average().save(f"state{i_q + 1}")
                else:
                    I_st[i_q].buffer(len(idle_times_cycles)).buffer(len(flux_amp_array)).average().save(f"I{i_q + 1}")
                    Q_st[i_q].buffer(len(idle_times_cycles)).buffer(len(flux_amp_array)).average().save(f"Q{i_q + 1}")

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
    return _acquire(machine, prog, sweep_axes, num_shots=num_shots, timeout=timeout, log=log)
