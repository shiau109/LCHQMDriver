from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters
from typing import List, Optional, Literal


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    qubit_sweep: str = "q0"
    """Qubit to use for detection. Default is 100."""
    qubit_fixed: str = "q1"
    """Qubit to use for detection. Default is 100."""
    qubit_control: str = "q0"
    """Qubit to use for turn on CZ. Default is q0."""
    qubit_pair: str = "q0-1"
    """coupler to use for change zz interaction shift. Default is 100."""
    operation: str = "cz_square"
    """Type of operation to perform. Default is "cz"."""
    operation_len_in_ns: Optional[int] = None
    """Length of the operation in ns. Default is the predefined pulse length."""
    readout_angle_point: int = 20
    """Readout angle points. Default is 20 points."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
