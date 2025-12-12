from typing import Optional
from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    max_driving_time_ns: int = 1000
    """Maximum driving time in nanoseconds. Default is 1000 ns."""
    min_driving_time_ns: int = 0
    """Minimum driving time in nanoseconds. Default is 0 ns."""
    driving_time_step: int = 40
    """Step size for driving time in nanoseconds. Default is 40 ns."""
    operation: str = "saturation"
    """Type of operation to perform. Default is "saturation"."""
    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on. Default is None."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
