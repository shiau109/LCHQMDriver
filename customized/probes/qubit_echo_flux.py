"""T2 Echo vs Flux spectrum acquisition probe: vendor code only (qm/quam)."""

from typing import Callable, Optional, List
import numpy as np
import xarray as xr
from qm.qua import *

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    wait_times_cycles,
    flux_amps_v: List[float],
    num_shots: int,
    reset_type: str = "thermal",
    use_state_discrimination: bool = False,
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the T2 Echo vs Flux QUA program. Returns (program, sweep_axes)."""
    wait_times_cycles = np.unique(np.asarray(wait_times_cycles))
    flux_amps_v = np.asarray(flux_amps_v)
    num_qubits = len(qubits)

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "flux_amp": xr.DataArray(flux_amps_v, attrs={"long_name": "flux pulse amplitude", "units": "V"}),
        "wait_time_ns": xr.DataArray(4 * wait_times_cycles, attrs={"long_name": "total wait time", "units": "ns"}),
    }

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        t = declare(int)
        v = declare(fixed)

        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        for multiplexed_qubits in qubits.batch():
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)

                with for_each_(v, flux_amps_v):
                    with for_each_(t, wait_times_cycles):
                        # Qubit reset
                        for i, qubit in multiplexed_qubits.items():
                            qubit.reset(reset_type, simulate, log_callable=log)
                        align()

                        # Echo sequence: x90 -> [wait(t) + Z(v)] -> x180 -> [wait(t) + Z(v)] -> x90
                        for i, qubit in multiplexed_qubits.items():
                            qubit.align()
                            play("x90", qubit.xy.name)
                            qubit.align()

                            if hasattr(qubit, "z") and qubit.z is not None:
                                play("const" * amp(v), qubit.z.name, duration=t)
                            wait(t, qubit.xy.name)
                            qubit.align()

                            play("x180", qubit.xy.name)
                            qubit.align()

                            if hasattr(qubit, "z") and qubit.z is not None:
                                play("const" * amp(v), qubit.z.name, duration=t)
                            wait(t, qubit.xy.name)
                            qubit.align()

                            play("x90", qubit.xy.name)
                            qubit.align()

                        # Readout
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
                    state_st[i].buffer(len(wait_times_cycles)).buffer(len(flux_amps_v)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(wait_times_cycles)).buffer(len(flux_amps_v)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(wait_times_cycles)).buffer(len(flux_amps_v)).average().save(f"Q{i + 1}")

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
