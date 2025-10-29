from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from customized.common_parameters import CommonFluxParameters
from typing import Optional

from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    idle_time_in_ns: Optional[float] = None
    """Idle time in ns. Default is None."""
    max_idle_time_in_ns: float = 20000
    """Max idle time in ns. Default is 20000."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
