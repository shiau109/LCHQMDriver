"""Single-excitation flux-chevron acquisition probe: vendor code only (qm/quam) -
no qualibrate, no scqo, no scqat.

Adapted from `calibrations/19_chevron_11_02.py` (the two-qubit CZ chevron). The
flux pulse still sweeps amplitude x duration on the control qubit's z line and
both qubits are still read out, but only **one** qubit of the pair is excited with
`x180` (selected by `drive_role`, default the control qubit) instead of preparing
|11>. There is no fit/state-writeback downstream; the node renders a 2D color map.

With state discrimination both qubits are read out 2-level and the saved data is the
joint two-qubit populations P00, P01, P10, P11 (first digit = control, second =
target) as variables `state_gg/state_ge/state_eg/state_ee` -- not the independent
single-qubit averages. Without state discrimination the raw I/Q of each qubit is saved.

The sub-4ns flux-pulse granularity uses the baking tool (`qualang_tools.bakery`):
short segments (1..16 ns) are baked into the config, and longer pulses combine a
baked tail with a dynamically stretched (multiple-of-4ns) `play`.
"""

from typing import Callable, Optional

import numpy as np
import xarray as xr
from qm.qua import *

from qualang_tools.bakery import baking
from qualang_tools.loops import from_array

from customized.probes._lib import acquire as _acquire


def baked_waveform(qubit, baked_config, base_level: float = 0.5, max_samples: int = 16):
    """Create truncated baked waveforms for the chevron flux pulse.

    Generates a list of baking objects, each containing an incrementally longer flux pulse
    (1..max_samples samples) at the specified base_level. Each baked pulse is registered
    as an operation named "flux_pulse{i}" on the provided qubit z line.

    Copied from `calibration_utils.chevron_cz.parameters.baked_waveform` so this probe
    stays free of qualibrate imports.

    Returns a list of baking objects; index i corresponds to a pulse of i+1 samples.
    """
    pulse_segments = []
    waveform = [base_level] * max_samples
    for i in range(1, max_samples + 1):
        with baking(baked_config, padding_method="right") as b:
            wf = waveform[:i]
            b.add_op(f"flux_pulse{i}", qubit.z.name, wf)
            b.play(f"flux_pulse{i}", qubit.z.name)
        pulse_segments.append(b)
    return pulse_segments


def build_program(
    machine,
    qubit_pairs,
    *,
    amplitudes,
    times_cycles,
    num_shots: int,
    reset_type: str,
    use_state_discrimination: bool,
    drive_role: str = "control",
    simulate: bool = False,
):
    """Build the single-excitation flux-chevron QUA program.

    Returns (program, sweep_axes, baked_config). The returned `baked_config` carries
    the baked flux-pulse operations and MUST be the config used to execute (pass it to
    `acquire(..., config=baked_config)`); a freshly generated config would lack them.

    `amplitudes` is the flux-pulse amplitude pre-factor sweep (centred on 1.0);
    `times_cycles` is the pulse-duration sweep in ns; `qubit_pairs` is a BatchableList
    of qubit pairs (`qubit_pairs.batch()` / `.get_names()`). `drive_role` selects which
    qubit of each pair receives the x180 ("control" or "target").
    """
    num_qubit_pairs = len(qubit_pairs)

    # The flux-pulse base amplitude that brings |11> into resonance with |02> for each pair.
    pulse_amplitudes = {}
    for qp in qubit_pairs:
        detuning = qp.qubit_control.xy.RF_frequency - qp.qubit_target.xy.RF_frequency - qp.qubit_target.anharmonicity
        pulse_amplitudes[qp.name] = float(np.sqrt(-detuning / qp.qubit_control.freq_vs_flux_01_quad_term))

    sweep_axes = {
        "qubit_pair": xr.DataArray(qubit_pairs.get_names()),
        "amplitude": xr.DataArray(amplitudes, attrs={"long_name": "amplitudes of the flux pulse"}),
        "time": xr.DataArray(times_cycles, attrs={"long_name": "pulse duration", "units": "ns"}),
    }

    baked_config = machine.generate_config()

    # Pre-compute the baked short segments (1..16 samples) for each control qubit in the pairs.
    baked_signals = {
        qp.qubit_control.name: baked_waveform(
            qp.qubit_control, baked_config, base_level=pulse_amplitudes[qp.name], max_samples=16
        )
        for qp in qubit_pairs
    }

    with program() as prog:
        t = declare(int)  # QUA variable for the flux pulse segment index
        a = declare(fixed)
        t_left_ns = declare(int)
        t_cycles = declare(int)
        I_c, I_c_st, Q_c, Q_c_st, n, n_st = machine.declare_qua_variables()
        I_t, I_t_st, Q_t, Q_t_st, _, _ = machine.declare_qua_variables()
        if use_state_discrimination:
            # Per-shot single-qubit outcomes (both qubits read out 2-level -> {0, 1}).
            state_c = [declare(int) for _ in range(num_qubit_pairs)]
            state_t = [declare(int) for _ in range(num_qubit_pairs)]
            # Joint two-qubit indicators (first digit = control, second = target);
            # averaged over shots they give the P00/P01/P10/P11 populations.
            ind_gg = declare(int)  # 00
            ind_ge = declare(int)  # 01
            ind_eg = declare(int)  # 10
            ind_ee = declare(int)  # 11
            state_gg_st = [declare_stream() for _ in range(num_qubit_pairs)]
            state_ge_st = [declare_stream() for _ in range(num_qubit_pairs)]
            state_eg_st = [declare_stream() for _ in range(num_qubit_pairs)]
            state_ee_st = [declare_stream() for _ in range(num_qubit_pairs)]

        for multiplexed_qubit_pairs in qubit_pairs.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qp in multiplexed_qubit_pairs.values():
                machine.initialize_qpu(target=qp.qubit_control)
                machine.initialize_qpu(target=qp.qubit_target)
            align()
            # Averaging loop
            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                # Pulse amplitude loop
                with for_(*from_array(a, amplitudes)):
                    ################################################################################################
                    # The duration argument in the play command can only produce pulses with duration multiple of  #
                    # 4ns. To overcome this limitation we use the baking tool from the qualang-tools package to    #
                    # generate pulses with 1ns granularity. To avoid creating custom waveforms for each iteration  #
                    # we combine baked pulses with dynamically stretched (multiple of 4ns) pulses.                 #
                    ################################################################################################
                    with for_(*from_array(t, times_cycles)):
                        for ii, qp in multiplexed_qubit_pairs.items():
                            # Qubit initialization
                            qp.qubit_control.reset(reset_type, simulate)
                            qp.qubit_target.reset(reset_type, simulate)
                            align()
                            # Excite only one qubit of the pair (single-excitation chevron).
                            if drive_role == "target":
                                qp.qubit_target.xy.play("x180")
                            else:
                                qp.qubit_control.xy.play("x180")

                            align()

                            # For the first 16ns we play baked pulses exclusively. Loop the time index until 16.
                            with if_(t <= 16):
                                with switch_(t):
                                    # Switch case to select the baked pulse with duration t ns
                                    for j in range(1, 17):
                                        with case_(j):
                                            baked_signals[qp.qubit_control.name][j - 1].run(
                                                amp_array=[(qp.qubit_control.z.name, a)]
                                            )

                            # For pulse durations above 16ns we combine baking with regular play statements.
                            with else_():
                                # We calculate the closest lower multiple of 4 of the time index
                                assign(t_cycles, t >> 2)  # Right shift by 2 is a quick way to divide by 4
                                # Calculate the duration to add to pulse multiple of 4.
                                assign(t_left_ns, t - (t_cycles << 2))  # left shift by 2 to multiply by 4
                                # Switch case with the 4 possible sequences:
                                with switch_(t_left_ns):
                                    # Play only the pulse multiple of 4
                                    with case_(0):
                                        align()
                                        p = pulse_amplitudes[qp.name]
                                        denom = qp.qubit_control.z.operations["const"].amplitude
                                        scale = (p / denom) * a
                                        qp.qubit_control.z.play(
                                            "const",
                                            duration=t_cycles,
                                            amplitude_scale=scale,
                                        )
                                    # Play the pulse multiple of 4 followed by the baked pulse of the missing duration
                                    for j in range(1, 4):
                                        with case_(j):
                                            align()
                                            p = pulse_amplitudes[qp.name]
                                            denom = qp.qubit_control.z.operations["const"].amplitude
                                            scale = (p / denom) * a
                                            with strict_timing_():
                                                qp.qubit_control.z.play(
                                                    "const",
                                                    duration=t_cycles,
                                                    amplitude_scale=scale,
                                                )
                                                baked_signals[qp.qubit_control.name][j - 1].run(
                                                    amp_array=[(qp.qubit_control.z.name, a)]
                                                )
                            align()

                            if use_state_discrimination:
                                qp.qubit_control.readout_state(state_c[ii])
                                qp.qubit_target.readout_state(state_t[ii])
                                # Joint-state indicators from the two binary outcomes:
                                #   ee(11)=c*t, eg(10)=c-ee, ge(01)=t-ee, gg(00)=1-c-t+ee
                                assign(ind_ee, state_c[ii] * state_t[ii])
                                assign(ind_eg, state_c[ii] - ind_ee)
                                assign(ind_ge, state_t[ii] - ind_ee)
                                assign(ind_gg, 1 - state_c[ii] - state_t[ii] + ind_ee)
                                save(ind_gg, state_gg_st[ii])
                                save(ind_ge, state_ge_st[ii])
                                save(ind_eg, state_eg_st[ii])
                                save(ind_ee, state_ee_st[ii])
                            else:
                                qp.qubit_control.resonator.measure("readout", qua_vars=(I_c[ii], Q_c[ii]))
                                qp.qubit_target.resonator.measure("readout", qua_vars=(I_t[ii], Q_t[ii]))
                                save(I_c[ii], I_c_st[ii])
                                save(Q_c[ii], Q_c_st[ii])
                                save(I_t[ii], I_t_st[ii])
                                save(Q_t[ii], Q_t_st[ii])

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubit_pairs):
                if use_state_discrimination:
                    # Averaging the 0/1 indicators over shots yields the joint populations.
                    state_gg_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"state_gg{i}")
                    state_ge_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"state_ge{i}")
                    state_eg_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"state_eg{i}")
                    state_ee_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"state_ee{i}")
                else:
                    I_c_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"I_control{i}")
                    Q_c_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"Q_control{i}")
                    I_t_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"I_target{i}")
                    Q_t_st[i].buffer(len(times_cycles)).buffer(len(amplitudes)).average().save(f"Q_target{i}")

    return prog, sweep_axes, baked_config


def acquire(
    machine,
    prog,
    sweep_axes,
    *,
    num_shots: int,
    timeout: float,
    log: Optional[Callable] = None,
    config: Optional[dict] = None,
) -> xr.Dataset:
    """Connect to the QOP, execute the program and fetch the raw xr.Dataset.

    Pass the baked config returned by `build_program` as `config`; the shared
    execute-and-fetch helper would otherwise regenerate a config without the baked ops.
    """
    return _acquire(machine, prog, sweep_axes, num_shots=num_shots, timeout=timeout, log=log, config=config)
