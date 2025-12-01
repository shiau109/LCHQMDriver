from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from customized.common_parameters import CommonFluxParameters

from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    qubit_z_pulse: str = "q0"
    """Qubit unser test. Default is 1.0 MHz."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
