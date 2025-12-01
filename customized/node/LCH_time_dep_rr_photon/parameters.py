from typing import Optional

from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 50
    """Number of averages to perform. Default is 50."""
    xy_operation: str = "x180"
    """Operation to perform. Default is "x180"."""
    xy_operation_amplitude_factor: float = 0.1
    """Amplitude factor for the operation. Default is 0.1."""
    xy_operation_len_in_ns: Optional[int] = None
    """Length of the operation in ns. Default is the predefined pulse length."""
    xy_time_resolution_in_ns: int = 40
    """Resolution of Delay time between XY and RO pulses in ns. Default is 40 ns."""
    xy_max_delay_in_ns: int = 4000
    """Resolution of Delay time between XY and RO pulses in ns. Default is 40 ns."""
    max_frequency_in_mhz: float = 100.0
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_in_mhz: float = -100
    """Minimum frequency in MHz. Default is -250 MHz."""
    num_frequency_points: int = 101
    """Number of frequency points. Default is 51."""
    ro_operation: str = "readout"
    """Operation to perform. Default is "readout"."""
    rr_depletion_time: Optional[int] = None
    """Resonator depletion time in ns. Default is the predefined depletion time."""



class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
