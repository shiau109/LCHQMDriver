from typing import Optional

from qualibrate import NodeParameters
from qualibration_libs.parameters import CommonNodeParameters, QubitsExperimentNodeParameters

from calibration_utils.power_rabi.parameters import NodeSpecificParameters


class LCHNodeSpecificParameters(NodeSpecificParameters):
    """04b power-Rabi params plus single-qubit drive selection.

    Lab-tuned defaults are overridden here (NOT in the vendored
    calibration_utils file, which sync_official.py would revert)."""

    num_shots: int = 200
    """Number of averages to perform. Default is 200."""
    min_amp_factor: float = 0.0
    """Minimum amplitude factor for the operation. Default is 0.0."""
    max_amp_factor: float = 1.9
    """Maximum amplitude factor for the operation. Default is 1.9."""
    amp_factor_step: float = 0.05
    """Step size for the amplitude factor. Default is 0.05."""
    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on (e.g. "q4"). If None, all qubits are driven."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    LCHNodeSpecificParameters,
    QubitsExperimentNodeParameters,
):
    """Parameter set for LCH_power_rabi (single-pulse power Rabi with drive_qubit)."""
