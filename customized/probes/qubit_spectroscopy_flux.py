"""Qubit-spectroscopy-vs-flux acquisition probe: vendor code only (qm/quam) - no qualibrate, no scqo, no scqat.

Sweep a flux bias and the drive frequency and read out each qubit; the qubit line is fitted
flux-by-flux downstream to give a frequency(flux) trace. Optional single flux / xy source qubits:
when `z_source_qubit` / `xy_source_qubit` are None every measured qubit fluxes / drives itself.
"""

from typing import Callable, Optional

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
    dcs,
    operation: str,
    operation_len,
    operation_amp: float,
    num_shots: int,
    z_source_qubit: Optional[str] = None,
    xy_source_qubit: Optional[str] = None,
    multiplexed: bool = False,
):
    """Build the qubit-spectroscopy-vs-flux QUA program. Returns (program, sweep_axes).

    `dfs` is the drive-detuning sweep (Hz), `dcs` the flux-bias sweep (V); `qubits` is a
    BatchableList (see `_lib.select_qubits`). `z_source_qubit` / `xy_source_qubit` (names on
    `machine`, or None) select a single flux / xy source. `operation_len` (ns) overrides the
    driving qubit's operation length when not None.
    """
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)

    # Resolve the single flux / xy source qubits (if any). When None, each measured
    # qubit drives its own z- / xy-line (identical to the official 03b node).
    z_source = None if z_source_qubit is None else machine.qubits[z_source_qubit]
    xy_source = None if xy_source_qubit is None else machine.qubits[xy_source_qubit]

    # Saturation duration (Python-level): uniform when operation_len is given, else
    # taken from the driving qubit's operation length.
    ref_qubit = xy_source if xy_source is not None else next(iter(qubits))
    operation_duration = (
        operation_len * u.ns if operation_len is not None
        else ref_qubit.xy.operations[operation].length * u.ns
    )

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "qubit frequency", "units": "Hz"}),
        "flux_bias": xr.DataArray(dcs, attrs={"long_name": "flux bias", "units": "V"}),
    }

    with program() as prog:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        df = declare(int)  # QUA variable for the qubit drive frequency detuning
        dc = declare(fixed)  # QUA variable for the flux dc level

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                with for_(*from_array(df, dfs)):
                    with for_(*from_array(dc, dcs)):
                        # Qubit initialization: thermalize to the ground state.
                        for i, qubit in multiplexed_qubits.items():
                            qubit.reset_qubit_thermal()
                        # Update the drive frequency on whichever xy-line plays.
                        if xy_source is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                        else:
                            xy_source.xy.update_frequency(df + xy_source.xy.intermediate_frequency)
                        align()

                        # Bring the qubit(s) to the flux point during the saturation pulse.
                        if z_source is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.z.play(
                                    "const",
                                    amplitude_scale=dc / qubit.z.operations["const"].amplitude,
                                    duration=operation_duration,
                                )
                        else:
                            z_source.z.play(
                                "const",
                                amplitude_scale=dc / z_source.z.operations["const"].amplitude,
                                duration=operation_duration,
                            )
                        # Apply the saturation drive: from each qubit, or a single xy source.
                        if xy_source is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.xy.play(operation, amplitude_scale=operation_amp, duration=operation_duration)
                        else:
                            xy_source.xy.play(operation, amplitude_scale=operation_amp, duration=operation_duration)
                        align()

                        # Readout every measured qubit's resonator.
                        for i, qubit in multiplexed_qubits.items():
                            qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                            save(I[i], I_st[i])
                            save(Q[i], Q_st[i])

            # Measure sequentially
            if not multiplexed:
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st[i].buffer(len(dcs)).buffer(len(dfs)).average().save(f"I{i + 1}")
                Q_st[i].buffer(len(dcs)).buffer(len(dfs)).average().save(f"Q{i + 1}")

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
