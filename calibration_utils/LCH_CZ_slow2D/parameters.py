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
    qubit_pair: str = "q0-1"
    """coupler to use for change zz interaction shift. Default is 100."""
    operation: str = "cz_square"
    """Type of operation to perform. Default is "cz"."""

    min_qubit_amp_in_v: float = -0.1
    """Minimum qubit bias offset in volts. Default is -0.5 V."""
    max_qubit_amp_in_v: float = 0.1
    """Maximum qubit bias offset in volts. Default is 0.5 V."""
    num_qubit_amp_points: int = 51
    """Number of qubit amplitude points. Default is 51."""


    min_coupler_amp_in_v: float = -0.1
    """Minimum coupler bias offset in volts. Default is -0.5 V."""
    max_coupler_amp_in_v: float = 0.1
    """Maximum coupler bias offset in volts. Default is 0.5 V."""
    num_coupler_amp_points: int = 51
    """Number of coupler amplitude points. Default is 51."""

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
