"""DRAG Equator calibration acquisition probe: vendor code only (qm/quam)."""

from typing import Callable, Optional, List
import numpy as np
import xarray as xr
from qm.qua import *

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    num_shots: int,
    beta_array: List[float],
    pulse_repetitions: int,
    use_state_discrimination: bool,
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the DRAG equator QUA program. Returns (program, sweep_axes)."""
    num_qubits = len(qubits)
    beta_array = np.asarray(beta_array)

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "seq_idx": xr.DataArray(np.array([0, 1, 2])),
        "beta": xr.DataArray(beta_array, attrs={"long_name": "DRAG beta pre-factor", "units": ""}),
    }

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        a = declare(fixed)  # DRAG beta scale factor
        seq = declare(int)
        count = declare(int)

        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        for multiplexed_qubits in qubits.batch():
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                with for_(*from_array(a, beta_array)):
                    with for_(seq, 0, seq < 3, seq + 1):
                        # Qubit initialization
                        for i_q, qubit in multiplexed_qubits.items():
                            qubit.reset("thermal", simulate, log_callable=log)
                        align()

                        # Play sequence
                        for i_q, qubit in multiplexed_qubits.items():
                            qubit.align()
                            # Initial X90 pulse
                            play("x90" * amp(1, 0, 0, a), qubit.xy.name)
                            
                            # Odd number of pi pulses
                            with if_(seq == 0):
                                with for_(count, 0, count < pulse_repetitions, count + 1):
                                    play("y180" * amp(1, 0, 0, a), qubit.xy.name)
                            with if_(seq == 1):
                                with for_(count, 0, count < pulse_repetitions, count + 1):
                                    play("y180" * amp(-1, 0, 0, -a), qubit.xy.name)
                            with if_(seq == 2):
                                with for_(count, 0, count < pulse_repetitions, count + 1):
                                    play("x180" * amp(1, 0, 0, a), qubit.xy.name)
                            qubit.align()

                        # Measurement
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
                    state_st[i_q].buffer(3).buffer(len(beta_array)).average().save(f"state{i_q + 1}")
                else:
                    I_st[i_q].buffer(3).buffer(len(beta_array)).average().save(f"I{i_q + 1}")
                    Q_st[i_q].buffer(3).buffer(len(beta_array)).average().save(f"Q{i_q + 1}")

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
