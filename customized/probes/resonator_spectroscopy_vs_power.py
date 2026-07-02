"""Resonator-spectroscopy-vs-power acquisition probe: vendor code only (qm/quam) -
no qualibrate, no scqo, no scqat.

2-D resonator spectroscopy vs readout power: sweep the readout intermediate
frequency around each resonator's current IF and, at each detuning, sweep the
readout amplitude pre-factor (`amps`, mapped to `power_dbm` for the axis). The
|IQ| dip locates the resonance at every power. No qubit reset - the resonator is
measured directly.

This mirrors the official `02b_resonator_spectroscopy_vs_power` sequence with one
change: the averaging loop `for_(n, ...)` is the **innermost** loop (as in
`LCH_resonator_spectroscopy_flux`), not the outermost. The caller must have set
each resonator's base output power to the sweep's max power *before* generating
the config (the qualibrate shell does this via `tracked_updates`); this probe
only builds the amplitude/frequency sweep, keeping it framework-free.
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
    amps,
    power_dbm,
    num_shots: int,
):
    """Build the resonator-spectroscopy-vs-power QUA program. Returns (program, sweep_axes).

    `dfs` is the readout-frequency detuning sweep in Hz (relative to each
    resonator's current IF); `amps` is the readout-amplitude pre-factor sweep
    (dimensionless, within [-2, 2)); `power_dbm` is the matching readout-power axis
    in dBm (same length as `amps`); `qubits` is a BatchableList (see
    `_lib.select_qubits`).
    """
    u = unit(coerce_to_integer=True)
    num_qubits = len(qubits)
    n_avg = num_shots

    sweep_axes = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "readout frequency", "units": "Hz"}),
        "power": xr.DataArray(power_dbm, attrs={"long_name": "readout power", "units": "dBm"}),
    }

    with program() as prog:
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        a = declare(fixed)  # QUA variable for the readout amplitude pre-factor
        df = declare(int)  # QUA variable for the readout frequency detuning
        idx = declare(int)  # progress index over the outer detuning loop

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                machine.initialize_qpu(target=qubit)
            align()

            assign(idx, 0)
            with for_(*from_array(df, dfs)):  # sweep the frequency (outer)
                # Save the detuning-point counter for the progress bar
                save(idx, n_st)
                assign(idx, idx + 1)
                for i, qubit in multiplexed_qubits.items():
                    rr = qubit.resonator
                    # Update the resonator frequencies for all resonators
                    rr.update_frequency(df + rr.intermediate_frequency)
                    with for_each_(a, amps):  # sweep the readout amplitude / power
                        # Average innermost: repeat the measurement n_avg times per point
                        with for_(n, 0, n < n_avg, n + 1):
                            # readout the resonator at the swept amplitude
                            rr.measure("readout", qua_vars=(I[i], Q[i]), amplitude_scale=a)
                            # wait for the resonator to deplete
                            rr.wait(rr.depletion_time * u.ns)
                            # save data
                            save(I[i], I_st[i])
                            save(Q[i], Q_st[i])
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                # Average the innermost n_avg shots, then buffer power then detuning
                I_st[i].buffer(n_avg).map(FUNCTIONS.average()).buffer(len(amps)).buffer(len(dfs)).save(f"I{i + 1}")
                Q_st[i].buffer(n_avg).map(FUNCTIONS.average()).buffer(len(amps)).buffer(len(dfs)).save(f"Q{i + 1}")

    return prog, sweep_axes


def acquire(
    machine,
    prog,
    sweep_axes,
    *,
    num_detuning_points: int,
    timeout: float,
    log: Optional[Callable] = None,
) -> xr.Dataset:
    """Connect to the QOP, execute the program and fetch the raw xr.Dataset.

    The progress counter tracks the outer detuning loop (the `n` stream carries the
    detuning index here, since the averaging loop is innermost), so
    `num_detuning_points` is the progress total.
    """
    return _acquire(machine, prog, sweep_axes, num_shots=num_detuning_points, timeout=timeout, log=log)
