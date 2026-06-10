from typing import Optional

from qualibrate import NodeParameters
from qualibration_libs.parameters import CommonNodeParameters, QubitsExperimentNodeParameters

from calibration_utils.power_rabi.parameters import NodeSpecificParameters


class LCHNodeSpecificParameters(NodeSpecificParameters):
    """04b power-Rabi params plus single-qubit drive selection."""

    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on (e.g. "q4"). If None, all qubits are driven."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    LCHNodeSpecificParameters,
    QubitsExperimentNodeParameters,
):
    """Parameter set for LCH_power_rabi (single-pulse power Rabi with drive_qubit)."""
