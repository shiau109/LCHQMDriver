from typing import ClassVar, Literal, Optional

from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import CommonNodeParameters, QubitPairExperimentNodeParameters


class LCHNodeSpecificParameters(RunnableParameters):
    """Fixed-time qubit-flux x coupler-flux (single-excitation) 2D parameters.

    Like the single-excitation flux chevron (LCH_pair_qq_chevron), but the pulse duration
    is fixed and two flux amplitudes are swept -- the coupler flux (x axis) and a qubit
    flux (y axis, on the `flux_role` qubit's z line) -- forming a 2D color map. There is
    no fit and no state writeback, so calibration-specific knobs (e.g. update_all_pulses)
    are intentionally absent.
    """

    num_shots: int = 50
    """Number of averages to perform. Default is 50."""
    coupler_operation: str = "const"
    """Coupler pulse operation to play. Default is "const"."""
    qubit_operation: str = "const"
    """Qubit z-line pulse operation to play. Default is "const"."""
    flux_time: Optional[int] = None
    """Shared fixed flux-pulse duration in ns (multiple of 4, >= 16). None uses each op's native length (100 ns)."""
    flux_role: Literal["control", "target"] = "control"
    """Which qubit of each pair carries the qubit flux pulse (y axis). Default is "control"."""
    amp_mode: Literal["absolute", "prefactor"] = "absolute"
    """How both sweeps are read: "absolute" volts (emitted pulse = a V, |a/ref| < 2 enforced) or unitless "prefactor" (amplitude_scale)."""
    coupler_amp_start: float = -0.1
    """Start of the coupler flux amplitude sweep, x axis (volts if absolute, else prefactor). Default is -0.05."""
    coupler_amp_end: float = 0.1
    """End (exclusive) of the coupler flux amplitude sweep. Default is 0.05."""
    coupler_amp_step: float = 0.01
    """Step of the coupler flux amplitude sweep. Default is 0.01."""
    qubit_amp_start: float = -0.1
    """Start of the qubit flux amplitude sweep, y axis (volts if absolute, else prefactor). Default is -0.1."""
    qubit_amp_end: float = 0.1
    """End (exclusive) of the qubit flux amplitude sweep. Default is 0.1."""
    qubit_amp_step: float = 0.01
    """Step of the qubit flux amplitude sweep. Default is 0.01."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""
    drive_role: Literal["control", "target"] = "control"
    """Which qubit of each pair receives the x180. Default is "control"."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    LCHNodeSpecificParameters,
    QubitPairExperimentNodeParameters,
):
    """Parameter set for pair_qcq_fixed_time (fixed-time qubit-flux x coupler-flux 2D sweep)."""

    targets_name: ClassVar[str] = "qubit_pairs"
