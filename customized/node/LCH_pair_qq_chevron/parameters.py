from typing import ClassVar, Literal

from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import CommonNodeParameters, QubitPairExperimentNodeParameters


class LCHNodeSpecificParameters(RunnableParameters):
    """Single-excitation flux-chevron parameters.

    Same flux-pulse amplitude x duration sweep as the two-qubit CZ chevron
    (19_chevron_11_02), but only one qubit of the pair is excited (`drive_role`).
    There is no fit and no state writeback, so calibration-specific knobs
    (e.g. update_all_pulses) are intentionally absent.
    """

    num_shots: int = 50
    """Number of averages to perform. Default is 100."""
    op_time_start: int = 1
    """Start of the flux-pulse duration sweep, in ns. Default is 1."""
    op_time_end: int = 100
    """End (exclusive) of the flux-pulse duration sweep, in ns. Default is 100."""
    amp_ratio_start: float = 0.8
    """Start of the flux-pulse amplitude pre-factor sweep. Default is 0.9."""
    amp_ratio_end: float = 1.2
    """End (exclusive) of the flux-pulse amplitude pre-factor sweep. Default is 1.1."""
    amp_step: float = 0.01
    """Step of the flux-pulse amplitude pre-factor sweep. Default is 0.003."""
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
    """Parameter set for LCH_pair_qq_chevron (single-excitation flux chevron)."""

    targets_name: ClassVar[str] = "qubit_pairs"
