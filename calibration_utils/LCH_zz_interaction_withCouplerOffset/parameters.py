from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters
from typing import List, Optional, Literal


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    detector_qubit: str = None
    """Qubit to use for detection. Default is 100."""
    source_qubit: str = None
    """Qubit to use for create zz interaction shift. Default is 100."""
    qubit_pair: str = None
    """coupler to use for change zz interaction shift. Default is 100."""
    coupler_offset: float = 0.0
    """Offset to apply to the coupler. Default is 0.0."""
    
class Parameters(
    NodeParameters,
    CommonNodeParameters,
    IdleTimeNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
