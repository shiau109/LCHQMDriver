from typing import Optional

from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """Reset-check (power-Rabi-shaped reset diagnostic) parameters.

    Sweeps the `operation` drive amplitude pre-factor to prepare a continuum of excited
    populations, then plays the reset macro under test and reads out. Each amplitude is
    measured with the reset macro off then on; there is no fit and no state writeback.
    """

    num_shots: int = 200
    """Number of averages to perform. Default is 200."""
    min_amp_factor: float = 0.0
    """Minimum amplitude factor for the operation. Default is 0.0."""
    max_amp_factor: float = 1.9
    """Maximum amplitude factor for the operation. Default is 1.9."""
    amp_factor_step: float = 0.05
    """Step size for the amplitude factor. Default is 0.05."""
    operation: str = "x180"
    """Drive operation whose amplitude is swept for state prep. Default is "x180"."""
    drive_qubit: Optional[str] = None
    """Qubit to drive and reset (e.g. "q2"). If None, all selected qubits are driven/reset."""
    reset_operation: str = "reset"
    """Macro key applied on the driven qubit(s) in the reset="on" branch
    (`qubit.macros[reset_operation].apply()`). Must be invokable with no extra args.
    Default is "reset"."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    """Parameter set for LCH_qc_reset_check (power-Rabi-shaped reset diagnostic).

    `qubits` (from QubitsExperimentNodeParameters) is the measured set read out each shot;
    `reset_type`/`simulate`/`timeout`/`load_data_id`/`multiplexed` come from
    CommonNodeParameters.
    """
