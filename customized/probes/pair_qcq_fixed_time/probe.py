"""Fixed-time qubit-flux x coupler-flux acquisition probe: vendor code only (qm/quam) -
no qualibrate, no scqo, no scqat.

A fixed-time 2D variant of `customized.probes.pair_qq_chevron`. Instead of sweeping a flux
amplitude x duration, here the **duration is fixed** and **two flux amplitudes are
swept**, forming the x/y axes of a 2D color map:

  - x axis: the **coupler** flux amplitude (played on `qp.coupler`),
  - y axis: a **qubit** flux amplitude (played on the `flux_role` qubit's `z` line,
    control or target).

Both flux pulses play simultaneously over the same fixed window (the dual-flux pattern
from `calibrations/LCH_iswap_fixed_time_search.py`). One qubit of the pair is excited
with `x180` (selected by `drive_role`, default the control qubit); both qubits are read
out. There is no fit/state-writeback downstream; the node renders a 2D color map.

The flux pulses ride on top of the idle DC biases set by `machine.initialize_qpu`. The
duration is fixed (a multiple of 4 ns), so no baking is needed -- the QUA
`play(..., duration=...)` override is enough.

Amplitude sweep (`amp_mode`, applied to BOTH channels):
  - "absolute": the sweep values are pulse amplitudes in volts. Each channel plays
    `amplitude_scale = a / ref` where `ref` is that channel op's stored amplitude, so the
    emitted pulse equals the swept value. The resulting scale must stay inside QUA's
    (-2, 2) dynamic-amplitude range or a ValueError is raised before building.
  - "prefactor": the sweep values are used directly as the unitless `amplitude_scale`.

With state discrimination both qubits are read out 2-level and the saved data is the
joint two-qubit populations P00/P01/P10/P11 (first digit = control, second = target) as
variables `state_gg/state_ge/state_eg/state_ee`. Without state discrimination the raw
I/Q of each qubit is saved.
"""

from typing import Callable, Optional

import numpy as np
import xarray as xr
from qm.qua import *

from qualang_tools.loops import from_array

from customized.probes._lib import acquire as _acquire

# Largest magnitude QUA accepts for a dynamic `amplitude_scale` (the fixed-point range is (-2, 2)).
_MAX_AMP_SCALE = 2.0


def _flux_qubit(qp, flux_role: str):
    """Return the qubit of the pair whose z line carries the qubit flux pulse."""
    return qp.qubit_target if flux_role == "target" else qp.qubit_control


def build_program(
    machine,
    qubit_pairs,
    *,
    coupler_amplitudes,
    qubit_amplitudes,
    coupler_operation: str = "swap_01_10_square",
    qubit_operation: str = "const",
    flux_time: Optional[int] = None,
    flux_role: str = "control",
    amp_mode: str = "absolute",
    num_shots: int,
    reset_type: str,
    use_state_discrimination: bool,
    drive_role: str = "control",
    simulate: bool = False,
):
    """Build the fixed-time qubit-flux x coupler-flux QUA program.

    Returns (program, sweep_axes). The plain `machine.generate_config()` already carries
    both flux operations, so no special (baked) config is needed -- execute with
    `acquire(..., config=None)`.

    `coupler_amplitudes` / `qubit_amplitudes` are the two flux sweeps (x / y of the 2D
    map); their meaning depends on `amp_mode` (see module docstring). `coupler_operation`
    is the coupler op (default "swap_01_10_square"); `qubit_operation` is the qubit z op
    (default "const"). `flux_role` selects which qubit's z carries the qubit flux pulse;
    `drive_role` selects which qubit receives the x180. `flux_time` is the shared fixed
    pulse duration in ns (multiple of 4, >= 16); None uses each op's native length.
    """
    num_qubit_pairs = len(qubit_pairs)

    if amp_mode not in ("absolute", "prefactor"):
        raise ValueError(f"amp_mode must be 'absolute' or 'prefactor', got {amp_mode!r}")
    if flux_role not in ("control", "target"):
        raise ValueError(f"flux_role must be 'control' or 'target', got {flux_role!r}")

    # Resolve the per-pair coupler and qubit-z op reference amplitudes (verify they exist).
    coupler_refs = {}
    qubit_refs = {}
    for qp in qubit_pairs:
        if qp.coupler is None:
            raise ValueError(f"Qubit pair {qp.name} has no coupler; cannot run a coupler-flux sweep.")
        if coupler_operation not in qp.coupler.operations:
            raise ValueError(
                f"Coupler of {qp.name} has no operation {coupler_operation!r}; "
                f"available: {list(qp.coupler.operations)}"
            )
        fq = _flux_qubit(qp, flux_role)
        if fq.z is None:
            raise ValueError(f"{flux_role} qubit of {qp.name} ({fq.name}) has no z line; cannot run a qubit-flux sweep.")
        if qubit_operation not in fq.z.operations:
            raise ValueError(
                f"z line of {fq.name} has no operation {qubit_operation!r}; "
                f"available: {list(fq.z.operations)}"
            )
        coupler_refs[qp.name] = float(qp.coupler.operations[coupler_operation].amplitude)
        qubit_refs[qp.name] = float(fq.z.operations[qubit_operation].amplitude)

    coupler_amplitudes = np.asarray(coupler_amplitudes, dtype=float)
    qubit_amplitudes = np.asarray(qubit_amplitudes, dtype=float)

    # Validate that, in absolute mode, both sweeps keep amplitude_scale within QUA's (-2, 2) range.
    if amp_mode == "absolute":
        for qp in qubit_pairs:
            for what, amps, ref in (
                ("coupler", coupler_amplitudes, coupler_refs[qp.name]),
                (f"{flux_role} qubit", qubit_amplitudes, qubit_refs[qp.name]),
            ):
                max_scale = float(np.max(np.abs(amps))) / abs(ref)
                if max_scale >= _MAX_AMP_SCALE:
                    raise ValueError(
                        f"Absolute {what} flux sweep for {qp.name} exceeds QUA's amplitude_scale range: "
                        f"max |a/ref| = {max_scale:.3f} >= {_MAX_AMP_SCALE} (ref = {ref} V). "
                        f"Reduce the amplitude range or use amp_mode='prefactor'."
                    )
    else:  # prefactor
        for what, amps in (("coupler", coupler_amplitudes), (f"{flux_role} qubit", qubit_amplitudes)):
            max_scale = float(np.max(np.abs(amps)))
            if max_scale >= _MAX_AMP_SCALE:
                raise ValueError(
                    f"Prefactor {what} flux sweep exceeds QUA's amplitude_scale range: "
                    f"max |a| = {max_scale:.3f} >= {_MAX_AMP_SCALE}."
                )

    # Shared fixed pulse duration in clock cycles (4 ns), or None to use each op's native length.
    duration_cycles = None
    if flux_time is not None:
        if flux_time % 4 != 0 or flux_time < 16:
            raise ValueError(f"flux_time must be a multiple of 4 ns and >= 16 ns, got {flux_time}.")
        duration_cycles = flux_time // 4

    amp_units = "V" if amp_mode == "absolute" else "prefactor"
    sweep_axes = {
        "qubit_pair": xr.DataArray(qubit_pairs.get_names()),
        # Outer loop -> y axis.
        "qubit_amplitude": xr.DataArray(
            qubit_amplitudes, attrs={"long_name": f"{flux_role} qubit flux amplitude", "units": amp_units}
        ),
        # Inner loop -> x axis.
        "coupler_amplitude": xr.DataArray(
            coupler_amplitudes, attrs={"long_name": "coupler flux amplitude", "units": amp_units}
        ),
    }

    with program() as prog:
        c_a = declare(fixed)  # swept coupler amplitude (volts if absolute, else amplitude_scale)
        q_a = declare(fixed)  # swept qubit-z amplitude (volts if absolute, else amplitude_scale)
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
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers).
            for qp in multiplexed_qubit_pairs.values():
                machine.initialize_qpu(target=qp.qubit_control)
                machine.initialize_qpu(target=qp.qubit_target)
            align()
            # Averaging loop
            with for_(n, 0, n < num_shots, n + 1):
                save(n, n_st)
                # Qubit-flux amplitude loop (outer -> y axis)
                with for_(*from_array(q_a, qubit_amplitudes)):
                    # Coupler-flux amplitude loop (inner -> x axis)
                    with for_(*from_array(c_a, coupler_amplitudes)):
                        for ii, qp in multiplexed_qubit_pairs.items():
                            # Qubit initialization
                            qp.qubit_control.reset(reset_type, simulate)
                            qp.qubit_target.reset(reset_type, simulate)
                            align()
                            # Excite only one qubit of the pair (single excitation).
                            if drive_role == "target":
                                qp.qubit_target.xy.play("x180")
                            else:
                                qp.qubit_control.xy.play("x180")
                            align()

                            # Two simultaneous flux pulses at the fixed duration, swept amplitudes.
                            fq = _flux_qubit(qp, flux_role)
                            c_scale = c_a / coupler_refs[qp.name] if amp_mode == "absolute" else c_a
                            q_scale = q_a / qubit_refs[qp.name] if amp_mode == "absolute" else q_a
                            if duration_cycles is None:
                                fq.z.play(qubit_operation, amplitude_scale=q_scale)
                                qp.coupler.play(coupler_operation, amplitude_scale=c_scale)
                            else:
                                fq.z.play(qubit_operation, amplitude_scale=q_scale, duration=duration_cycles)
                                qp.coupler.play(coupler_operation, amplitude_scale=c_scale, duration=duration_cycles)
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
                    # Inner buffer = coupler amplitude (x), outer buffer = qubit amplitude (y).
                    state_gg_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"state_gg{i}")
                    state_ge_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"state_ge{i}")
                    state_eg_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"state_eg{i}")
                    state_ee_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"state_ee{i}")
                else:
                    I_c_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"I_control{i}")
                    Q_c_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"Q_control{i}")
                    I_t_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"I_target{i}")
                    Q_t_st[i].buffer(len(coupler_amplitudes)).buffer(len(qubit_amplitudes)).average().save(f"Q_target{i}")

    return prog, sweep_axes


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

    No baking is involved, so `config` may be left as None and the shared helper falls
    back to `machine.generate_config()`.
    """
    return _acquire(machine, prog, sweep_axes, num_shots=num_shots, timeout=timeout, log=log, config=config)
