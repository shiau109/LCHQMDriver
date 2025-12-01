from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters, QubitPairsExperimentNodeParameters
from typing import List, Optional, Literal


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""

    operation: str = "cz_square"
    """Type of operation to perform. Default is "cz"."""
    operation_times: int = 1
    """Number of times to repeat the operation. Default is 1."""
    operation_gap_ns: int = 16
    """Number of times to repeat the operation. Default is 1."""
    readout_angle_point: int = 20
    """Readout angle points. Default is 20 points."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    QubitPairsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
