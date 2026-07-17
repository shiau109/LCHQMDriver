"""Tomography acquisition probe: vendor code only (qm/quam) - no qualibrate, no scqo.

Trains GMM and measures state tomography for XY gate characterization.
"""

from typing import Callable, Optional, Dict, Any, List
import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.units import unit

from customized.probes._lib import acquire as _acquire


def build_program(
    machine,
    qubits,
    *,
    num_training_shots: int,
    num_shots: int,
    gate_counts: List[int],
    symmetrized_readout: bool,
    qubit_configs: Dict[str, Dict[str, str]],
    simulate: bool = False,
    log: Optional[Callable] = None,
):
    """Build the Tomography QUA program. Returns (program, sweep_axes)."""
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)
    n_sym = 2 if symmetrized_readout else 1
    
    basis_coords = ["x", "y", "z"]
    sym_coords = ["reg", "inv"] if symmetrized_readout else ["reg"]

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "n_runs": xr.DataArray(np.arange(num_shots)),
        "gate_count": xr.DataArray(np.array(gate_counts)),
        "basis": xr.DataArray(basis_coords),
        "sym": xr.DataArray(sym_coords),
    }

    with program() as prog:
        I_g = [declare(fixed) for _ in range(num_qubits)]
        Q_g = [declare(fixed) for _ in range(num_qubits)]
        I_e = [declare(fixed) for _ in range(num_qubits)]
        Q_e = [declare(fixed) for _ in range(num_qubits)]
        I_tomo = [declare(fixed) for _ in range(num_qubits)]
        Q_tomo = [declare(fixed) for _ in range(num_qubits)]

        I_g_st = [declare_stream() for _ in range(num_qubits)]
        Q_g_st = [declare_stream() for _ in range(num_qubits)]
        I_e_st = [declare_stream() for _ in range(num_qubits)]
        Q_e_st = [declare_stream() for _ in range(num_qubits)]
        I_tomo_st = [declare_stream() for _ in range(num_qubits)]
        Q_tomo_st = [declare_stream() for _ in range(num_qubits)]

        shot = declare(int)
        gc_idx = declare(int)
        basis = declare(int)
        sym_mode = declare(int)
        i = declare(int)

        for multiplexed_qubits in qubits.batch():
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            # --- 1. Training (Single-Shot G/E) ---
            with for_(shot, 0, shot < num_training_shots, shot + 1):
                for i_q, qubit in multiplexed_qubits.items():
                    qubit.reset("thermal", simulate, log_callable=log)
                align()
                for i_q, qubit in multiplexed_qubits.items():
                    qubit.resonator.measure("readout", qua_vars=(I_g[i_q], Q_g[i_q]))
                    qubit.resonator.wait(qubit.resonator.depletion_time * u.ns)
                    save(I_g[i_q], I_g_st[i_q])
                    save(Q_g[i_q], Q_g_st[i_q])
                align()

            with for_(shot, 0, shot < num_training_shots, shot + 1):
                for i_q, qubit in multiplexed_qubits.items():
                    qubit.reset("thermal", simulate, log_callable=log)
                align()
                for i_q, qubit in multiplexed_qubits.items():
                    qubit.xy.play("x180")
                align()
                for i_q, qubit in multiplexed_qubits.items():
                    qubit.resonator.measure("readout", qua_vars=(I_e[i_q], Q_e[i_q]))
                    qubit.resonator.wait(qubit.resonator.depletion_time * u.ns)
                    save(I_e[i_q], I_e_st[i_q])
                    save(Q_e[i_q], Q_e_st[i_q])
                align()

            # --- 2. Tomography ---
            with for_(shot, 0, shot < num_shots, shot + 1):
                with for_each_(gc_idx, gate_counts):
                    with for_each_(basis, [0, 1, 2]):
                        with for_each_(sym_mode, [0, 1] if symmetrized_readout else [0]):
                            for i_q, qubit in multiplexed_qubits.items():
                                qubit.reset("thermal", simulate, log_callable=log)
                            align()

                            # (A) Apply init state
                            for i_q, qubit in multiplexed_qubits.items():
                                config = qubit_configs.get(qubit.name, {"init_state": "0", "target_gate": "X"})
                                init_state = config["init_state"]
                                if init_state == "1":
                                    qubit.xy.play("x180")
                                elif init_state == "+":
                                    qubit.xy.play("y90")
                                elif init_state == "-":
                                    qubit.xy.play("-y90")
                                elif init_state == "+i":
                                    qubit.xy.play("-x90")
                                elif init_state == "-i":
                                    qubit.xy.play("x90")
                            align()

                            # (B) Apply target gate repeated gc_idx times
                            with for_(i, 0, i < gc_idx, i + 1):
                                for i_q, qubit in multiplexed_qubits.items():
                                    config = qubit_configs.get(qubit.name, {"init_state": "0", "target_gate": "X"})
                                    target_gate = config["target_gate"]
                                    if target_gate == "X":
                                        qubit.xy.play("x180")
                                    elif target_gate == "X90":
                                        qubit.xy.play("x90")
                                    elif target_gate == "Y":
                                        qubit.xy.play("y180")
                                    elif target_gate == "Y90":
                                        qubit.xy.play("y90")
                                    elif target_gate in ("I", "Idle", "idle"):
                                        qubit.xy.wait(qubit.xy.operations["x180"].length // 4)
                            align()

                            # (C) Apply basis rotation
                            for i_q, qubit in multiplexed_qubits.items():
                                with if_(basis == 0):
                                    qubit.xy.play("y90")
                                with if_(basis == 1):
                                    qubit.xy.play("-x90")
                            align()

                            # (D) Apply inversion for symmetrized readout
                            with if_(sym_mode == 1):
                                for i_q, qubit in multiplexed_qubits.items():
                                    qubit.xy.play("x180")
                            align()

                            # (E) Measure
                            for i_q, qubit in multiplexed_qubits.items():
                                qubit.resonator.measure("readout", qua_vars=(I_tomo[i_q], Q_tomo[i_q]))
                                qubit.resonator.wait(qubit.resonator.depletion_time * u.ns)
                                save(I_tomo[i_q], I_tomo_st[i_q])
                                save(Q_tomo[i_q], Q_tomo_st[i_q])
                            align()

        with stream_processing():
            for i_q in range(num_qubits):
                I_g_st[i_q].buffer(num_training_shots).save(f"Ig{i_q + 1}")
                Q_g_st[i_q].buffer(num_training_shots).save(f"Qg{i_q + 1}")
                I_e_st[i_q].buffer(num_training_shots).save(f"Ie{i_q + 1}")
                Q_e_st[i_q].buffer(num_training_shots).save(f"Qe{i_q + 1}")

                I_tomo_st[i_q].buffer(n_sym).buffer(3).buffer(len(gate_counts)).buffer(num_shots).save(f"I_tomo{i_q + 1}")
                Q_tomo_st[i_q].buffer(n_sym).buffer(3).buffer(len(gate_counts)).buffer(num_shots).save(f"Q_tomo{i_q + 1}")

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
