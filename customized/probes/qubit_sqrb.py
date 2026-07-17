"""SQRB acquisition probe: vendor code only (qm/quam) - no qualibrate, no scqo.

Plays randomized Clifford sequences generated on the FPGA using Cayley tables,
ending with a recovery gate to return to the ground state.
"""

from typing import Callable, Optional, List
import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.bakery.randomized_benchmark_c1 import c1_table

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    num_random_sequences: int,
    num_shots: int,
    depths: List[int],
    max_circuit_depth: int,
    use_state_discrimination: bool,
    use_strict_timing: bool,
    seed: Optional[int] = None,
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the SQRB QUA program. Returns (program, sweep_axes)."""
    num_qubits = len(qubits)
    num_depths = len(depths)
    
    # List of recovery gates from the lookup table
    inv_gates = [int(np.where(c1_table[i, :] == 0)[0][0]) for i in range(24)]
    
    if seed is None:
        seed = 12345
        
    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "sequence_idx": xr.DataArray(np.arange(num_random_sequences)),
        "depth": xr.DataArray(np.array(depths)),
    }

    def generate_sequence():
        cayley = declare(int, value=c1_table.flatten().tolist())
        inv_list = declare(int, value=inv_gates)
        current_state = declare(int)
        step = declare(int)
        sequence = declare(int, size=max_circuit_depth + 1)
        inv_gate = declare(int, size=max_circuit_depth + 1)
        i = declare(int)
        rand = Random(seed=seed)

        assign(current_state, 0)
        with for_(i, 0, i < max_circuit_depth, i + 1):
            assign(step, rand.rand_int(24))
            assign(current_state, cayley[current_state * 24 + step])
            assign(sequence[i], step)
            assign(inv_gate[i], inv_list[current_state])

        return sequence, inv_gate

    def play_sequence(sequence_list, depth, qubit):
        i = declare(int)
        with for_(i, 0, i <= depth, i + 1):
            with switch_(sequence_list[i], unsafe=True):
                with case_(0):
                    qubit.xy.wait(qubit.xy.operations["x180"].length // 4)
                with case_(1):  # x180
                    qubit.xy.play("x180")
                with case_(2):  # y180
                    qubit.xy.play("y180")
                with case_(3):  # Z180
                    qubit.xy.play("y180")
                    qubit.xy.play("x180")
                with case_(4):  # Z90 X180 Z-180
                    qubit.xy.play("x90")
                    qubit.xy.play("y90")
                with case_(5):  # Z-90 Y-90 Z-90
                    qubit.xy.play("x90")
                    qubit.xy.play("-y90")
                with case_(6):  # Z-90 X180 Z-180
                    qubit.xy.play("-x90")
                    qubit.xy.play("y90")
                with case_(7):  # Z-90 Y90 Z-90
                    qubit.xy.play("-x90")
                    qubit.xy.play("-y90")
                with case_(8):  # X90 Z90
                    qubit.xy.play("y90")
                    qubit.xy.play("x90")
                with case_(9):  # X-90 Z-90
                    qubit.xy.play("y90")
                    qubit.xy.play("-x90")
                with case_(10):  # z90 X90 Z90
                    qubit.xy.play("-y90")
                    qubit.xy.play("x90")
                with case_(11):  # z90 X-90 Z90
                    qubit.xy.play("-y90")
                    qubit.xy.play("-x90")
                with case_(12):  # x90
                    qubit.xy.play("x90")
                with case_(13):  # -x90
                    qubit.xy.play("-x90")
                with case_(14):  # y90
                    qubit.xy.play("y90")
                with case_(15):  # -y90
                    qubit.xy.play("-y90")
                with case_(16):  # Z90
                    qubit.xy.play("-x90")
                    qubit.xy.play("y90")
                    qubit.xy.play("x90")
                with case_(17):  # -Z90
                    qubit.xy.play("-x90")
                    qubit.xy.play("-y90")
                    qubit.xy.play("x90")
                with case_(18):  # Y-90 Z-90
                    qubit.xy.play("x180")
                    qubit.xy.play("y90")
                with case_(19):  # Y90 Z90
                    qubit.xy.play("x180")
                    qubit.xy.play("-y90")
                with case_(20):  # Y90 Z-90
                    qubit.xy.play("y180")
                    qubit.xy.play("x90")
                with case_(21):  # Y-90 Z90
                    qubit.xy.play("y180")
                    qubit.xy.play("-x90")
                with case_(22):  # x90 Z-90
                    qubit.xy.play("x90")
                    qubit.xy.play("y90")
                    qubit.xy.play("x90")
                with case_(23):  # -x90 Z90
                    qubit.xy.play("-x90")
                    qubit.xy.play("y90")
                    qubit.xy.play("-x90")

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]
            
        depth = declare(int)
        saved_gate = declare(int)
        m = declare(int)
        m_st = declare_stream()

        for multiplexed_qubits in qubits.batch():
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(m, 0, m < num_random_sequences, m + 1):
                save(m, m_st)
                sequence_list, inv_gate_list = generate_sequence()

                with for_(*from_array(depth, depths)):
                    assign(saved_gate, sequence_list[depth])
                    assign(sequence_list[depth], inv_gate_list[depth - 1])

                    with for_(n, 0, n < num_shots, n + 1):
                        for i_q, qubit in multiplexed_qubits.items():
                            qubit.reset("thermal", simulate, log_callable=log)
                        align()

                        for i_q, qubit in multiplexed_qubits.items():
                            if use_strict_timing:
                                with strict_timing_():
                                    play_sequence(sequence_list, depth, qubit)
                            else:
                                play_sequence(sequence_list, depth, qubit)
                        align()

                        for i_q, qubit in multiplexed_qubits.items():
                            if use_state_discrimination:
                                qubit.readout_state(state[i_q])
                                save(state[i_q], state_st[i_q])
                            else:
                                qubit.resonator.measure("readout", qua_vars=(I[i_q], Q[i_q]))
                                save(I[i_q], I_st[i_q])
                                save(Q[i_q], Q_st[i_q])
                        align()
                    assign(sequence_list[depth], saved_gate)

        with stream_processing():
            m_st.save("n")
            for i_q in range(num_qubits):
                if use_state_discrimination:
                    state_st[i_q].buffer(num_shots).map(FUNCTIONS.average()).buffer(num_depths).buffer(num_random_sequences).save(f"state{i_q + 1}")
                else:
                    I_st[i_q].buffer(num_shots).map(FUNCTIONS.average()).buffer(num_depths).buffer(num_random_sequences).save(f"I{i_q + 1}")
                    Q_st[i_q].buffer(num_shots).map(FUNCTIONS.average()).buffer(num_depths).buffer(num_random_sequences).save(f"Q{i_q + 1}")

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
