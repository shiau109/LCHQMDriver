from typing import Optional
from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    time_of_flight_in_ns: Optional[int] = 380
    """Time of flight in nanoseconds. Default is 28 ns."""
    readout_length_in_ns: Optional[int] = 1000
    """Readout length in nanoseconds. Default is 1000 ns."""
    smearing: Optional[int] = 0
    """Smearing in nanoseconds. Default is 0 ns."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
