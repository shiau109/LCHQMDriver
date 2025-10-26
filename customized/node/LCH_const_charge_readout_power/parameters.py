from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 2000
    """Number of shots to perform. Default is 2000."""
    start_amp: float = 0.5
    """Start amplitude. Default is 0.5."""
    end_amp: float = 1.99
    """End amplitude. Default is 1.99."""
    num_amps: int = 10
    """Number of amplitudes to sweep. Default is 10."""
    charge_gate_in_v: float = 0.0
    """Charge gate voltage in V. Default is 0.0 V."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
