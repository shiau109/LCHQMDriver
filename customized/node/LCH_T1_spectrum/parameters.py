from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 1000
    """Number of averages to perform. Default is 1000."""
    max_flux_amp_in_v: float = 0.05
    """Minimum flux bias offset in volts. Default is -0.02 V."""
    min_flux_amp_in_v: float = -0.05
    """Minimum flux bias offset in volts. Default is -0.02 V."""
    num_flux_points: int = 21
    """Number of flux points. Default is 51."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    IdleTimeNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
