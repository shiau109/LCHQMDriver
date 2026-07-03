"""N-swap (swap-chain) x qubit-flux-amplitude acquisition probe: vendor code only
(qm/quam/qualang_tools) - no qualibrate, no scqo, no scqat.

A 2D variant of `customized.probes.qc_N_swap`: on top of the swap-count sweep (N, inner
axis) the **control-qubit flux amplitude of the swap macro is swept** (outer axis), the
same knob `customized.probes.pair_qcq_fixed_time` sweeps in its `swap_via_macro` mode.
Each swap of the chain is applied as `swap_pair.macros[swap_operation].apply(ctrl_amp=q_a)`:
`ctrl_amp` is the swept amplitude in **absolute volts** (the macro rescales its z flux
pulse by `ctrl_amp / ref`), while the coupler plays bare at its baked amplitude
(`cplr_amp=None`). Every swap in a chain uses the same swept amplitude.

Circuit per shot (for a swept amplitude a and swap count N):
  1. Initialize every involved qubit with `q.reset(reset_type, simulate)`
     (involved = measured qubits + the swap pair's control/target).
  2. State prep: `swap_pair.qubit_control.xy.play("x180")`.
  3. Repeat N times: `swap_pair.macros[swap_operation].apply(ctrl_amp=a)`, then idle the
     pair's flux lines for `operation_gap_ns` (if nonzero).
  4. Read out every measured qubit (state discrimination -> discriminated state, else raw I/Q).

Reading the measured qubits versus (amplitude, N) gives one 2D population map per qubit:
a swap-amplitude fine-tuning map by error amplification (more swaps amplify a small
amplitude miscalibration). Downstream, the node fits each qubit's population-vs-N curve
at every amplitude with a cosine (scqat SwapOscillationEstimator), giving the
swap-oscillation frequency versus amplitude; there is no state writeback.

The chosen macro must expose a string `flux_pulse` playable on the control qubit's z
line and accept `apply(ctrl_amp=...)` (e.g. the lab `ISwapImplementation`); its stored
z-pulse amplitude is the rescaling reference and must be nonzero.
"""

from typing import Callable, List, Optional

import numpy as np
import xarray as xr
from qm.qua import *

from qualang_tools.loops import from_array

from customized.probes._lib import acquire as _acquire

# Largest magnitude QUA accepts for a dynamic `amplitude_scale` (the fixed-point range is (-2, 2)).
_MAX_AMP_SCALE = 2.0

# OPX1000 LF-FEM "direct" output rail: a waveform peak at >= 0.5 V is clipped/corrupted at
# runtime (the simulator does NOT show this). Both the stored pulse and the emitted
# (swept) amplitude must stay below it.
_DAC_RAIL = 0.5


def _dedup_involved(measure_qubits, swap_pair) -> List:
    """Return the unique (by `.name`) set of qubit elements that must be initialized.

    The measured qubits need not include the swap pair's control/target, but all of them
    must be flux-initialized and reset at the start of each shot.
    """
    involved = []
    seen = set()
    for q in list(measure_qubits) + [swap_pair.qubit_control, swap_pair.qubit_target]:
        if q.name not in seen:
            seen.add(q.name)
            involved.append(q)
    return involved


def build_program(
    machine,
    measure_qubits,
    swap_pair,
    *,
    swap_operation: str,
    rounds_array,
    qubit_amplitudes,
    num_shots: int,
    reset_type: str,
    use_state_discrimination: bool,
    operation_gap_ns: int = 0,
    simulate: bool = False,
):
    """Build the N-swap x qubit-flux-amplitude QUA program.

    Returns ``(program, sweep_axes)``.

    `measure_qubits` is a plain list of qubit objects read out at the end of the circuit;
    `swap_pair` is a qubit-pair object whose `macros[swap_operation]` is applied each swap.
    `rounds_array` is the integer sweep over the number of swaps (N=0 allowed, giving just
    the x180 prep, inner axis); `qubit_amplitudes` is the control-qubit flux amplitude
    sweep in absolute volts (outer axis), passed to each swap as the macro's `ctrl_amp`.
    All measured qubits are read out within the same shot (joint / multiplexed readout),
    since they share one circuit.

    `operation_gap_ns` (multiple of 4, default 0) idles the swap pair's flux lines after
    each swap, so its flux pulse can settle before the next swap fires (the gap also
    separates the last swap from readout).
    """
    measure_qubits = list(measure_qubits)
    num_qubits = len(measure_qubits)
    rounds_array = np.asarray(rounds_array).astype(int)
    qubit_amplitudes = np.asarray(qubit_amplitudes, dtype=float)

    if operation_gap_ns < 0 or operation_gap_ns % 4 != 0:
        raise ValueError(f"operation_gap_ns must be a non-negative multiple of 4 ns, got {operation_gap_ns}.")
    gap_cycles = operation_gap_ns // 4

    involved = _dedup_involved(measure_qubits, swap_pair)

    # Validate the macro's swept-ctrl_amp path (the pair_qcq_fixed_time swap_via_macro
    # contract): the macro must exist, its z flux pulse must be playable and its stored
    # amplitude is the rescaling reference for the absolute-volt sweep.
    if swap_operation not in swap_pair.macros:
        raise ValueError(f"Pair {swap_pair.name} has no macro {swap_operation!r}; available: {list(swap_pair.macros)}.")
    flux_pulse_name = getattr(swap_pair.macros[swap_operation], "flux_pulse", None)
    ops = swap_pair.qubit_control.z.operations
    if not isinstance(flux_pulse_name, str) or flux_pulse_name not in ops:
        raise ValueError(
            f"Macro {swap_operation!r} on {swap_pair.name} has no z flux_pulse playable with ctrl_amp "
            f"(flux_pulse={flux_pulse_name!r})."
        )
    ref = abs(float(ops[flux_pulse_name].amplitude))
    if ref == 0.0:
        raise ValueError(
            f"Macro {swap_operation!r} on {swap_pair.name} has a zero-amplitude z flux_pulse "
            f"({flux_pulse_name!r}); cannot scale it by ctrl_amp."
        )
    if ref >= _DAC_RAIL:
        raise ValueError(
            f"Macro {swap_operation!r} z pulse {flux_pulse_name!r} on {swap_pair.name} has amplitude "
            f"{ref} V >= {_DAC_RAIL} V (OPX1000 'direct'-mode DAC rail): the waveform is clipped/"
            f"corrupted on hardware and the simulator hides it. Lower the pulse amplitude (<0.5 V)."
        )
    max_amp = float(np.max(np.abs(qubit_amplitudes)))
    if max_amp >= _DAC_RAIL:
        raise ValueError(
            f"Qubit flux amplitude sweep reaches {max_amp} V >= {_DAC_RAIL} V (OPX1000 'direct'-mode "
            f"DAC rail): the emitted pulse equals the swept value and is clipped/corrupted on hardware. "
            f"Keep the sweep below 0.5 V."
        )
    max_scale = max_amp / ref
    if max_scale >= _MAX_AMP_SCALE:
        raise ValueError(
            f"Qubit flux amplitude sweep for {swap_pair.name} exceeds QUA's amplitude_scale range: "
            f"max |a/ref| = {max_scale:.3f} >= {_MAX_AMP_SCALE} (macro z ref = {ref} V). "
            f"Reduce the amplitude range or raise the stored pulse amplitude."
        )

    sweep_axes = {
        "qubit": xr.DataArray([q.name for q in measure_qubits]),
        # Outer loop -> y axis.
        "qubit_amplitude": xr.DataArray(
            qubit_amplitudes, attrs={"long_name": "control qubit flux amplitude", "units": "V"}
        ),
        # Inner loop -> x axis.
        "round": xr.DataArray(rounds_array, attrs={"long_name": "number of swaps"}),
    }

    with program() as prog:
        # Macro to declare I, Q, n and their respective streams for the measured qubits.
        I, I_st, Q, Q_st, n, n_st = machine.declare_qua_variables()
        q_a = declare(fixed)  # swept ctrl flux amplitude (absolute volts)
        r = declare(int)  # swept swap count (current value from rounds_array)
        rr = declare(int)  # inner swap counter
        if use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        # Initialize the QPU in terms of flux points for every involved element.
        for q in involved:
            machine.initialize_qpu(target=q)
        align()

        with for_(n, 0, n < num_shots, n + 1):
            save(n, n_st)
            # Qubit-flux amplitude loop (outer -> y axis)
            with for_(*from_array(q_a, qubit_amplitudes)):
                # Swap-count loop (inner -> x axis)
                with for_(*from_array(r, rounds_array)):
                    # Initialization: thermalize / actively reset every involved qubit.
                    for q in involved:
                        q.reset(reset_type, simulate)
                    align()

                    # State prep: excite the swap pair's control qubit to |1>.
                    swap_pair.qubit_control.xy.play("x180")
                    align()

                    # Circuit body: N swaps on the pair, each at the swept ctrl amplitude
                    # (the coupler plays bare at its baked amplitude, cplr_amp=None).
                    # Dynamic loop bound on r -> N=0 skips the body entirely (baseline).
                    # `gap_cycles` idles the pair's flux lines between gate operations so
                    # each swap's flux pulse can settle before the next one fires.
                    with for_(rr, 0, rr < r, rr + 1):
                        swap_pair.macros[swap_operation].apply(ctrl_amp=q_a)
                        if gap_cycles > 0:
                            swap_pair.wait(gap_cycles)
                        align()

                    # Joint (multiplexed) readout of all measured qubits.
                    for i, qubit in enumerate(measure_qubits):
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
                # Inner buffer = swap count (x), outer buffer = qubit amplitude (y).
                if use_state_discrimination:
                    state_st[i].buffer(len(rounds_array)).buffer(len(qubit_amplitudes)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(rounds_array)).buffer(len(qubit_amplitudes)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(rounds_array)).buffer(len(qubit_amplitudes)).average().save(f"Q{i + 1}")

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
