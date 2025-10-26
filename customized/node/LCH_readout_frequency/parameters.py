from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 2000
    """Number of shots to perform. Default is 2000."""
    start_freq_in_mhz: float = -2
    """Start frequency. Default is -2 MHz."""
    end_freq_in_mhz: float = 2
    """End frequency. Default is 2 MHz."""
    frequency_step_in_mhz: float = 0.1
    """Frequency step. Default is 0.1 MHz."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
