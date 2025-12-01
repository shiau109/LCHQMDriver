from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters
from typing import Optional


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 1000
    """Number of averages to perform. Default is 1000."""
    prepare_gate: Optional[str] = None
    """Prepare gate to use for the qubit. Default is "X90"."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    IdleTimeNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
