from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters
from customized.common_parameters import CommonFluxParameters
from typing import List, Optional, Literal


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    detector_qubit: str = "q0"
    """Qubit to use for detection. Default is 100."""
    source_qubit: str = "q1"
    """Qubit to use for create zz interaction shift. Default is 100."""
    qubit_pair: str = "q0-1"
    """coupler to use for change zz interaction shift. Default is 100."""

    min_coupler_offset_in_v: float = -0.5
    """Minimum coupler bias offset in volts. Default is -0.5 V."""
    max_coupler_offset_in_v: float = 0.5
    """Maximum coupler bias offset in volts. Default is 0.5 V."""
    num_coupler_flux_points: int = 51
    """Number of coupler flux points. Default is 51."""
    readout_basis_operation: str = "-x90"
    """Readout basis operation. Default is -x90."""
class Parameters(
    NodeParameters,
    CommonNodeParameters,
    IdleTimeNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
