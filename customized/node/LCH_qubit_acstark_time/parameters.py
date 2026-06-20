from typing import Optional
from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    xy_operation: str = "x180"
    """Operation to perform. Default is "x180"."""
    xy_operation_amplitude_factor: float = 1
    """Amplitude factor for the operation. Default is 1."""
    xy_time_resolution_in_ns: int = 100
    """Step of the probe-delay sweep, in ns. Should be a multiple of 4 ns. Default is 100 ns."""
    xy_delay_start_in_ns: int = -100
    """Start of the probe delay relative to the resonator drive onset, in ns. May be NEGATIVE
    (the qubit probe fires before the drive). Default is -100 ns."""
    xy_delay_end_in_ns: int = 1000
    """End of the probe delay relative to the resonator drive onset, in ns. Default is 1000 ns."""
    max_frequency_in_mhz: float = 50
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_in_mhz: float = -100
    """Minimum frequency in MHz. Default is -100 MHz."""
    num_frequency_points: int = 31
    """Number of frequency points. Default is 31."""
    ro_operation: str = "readout"
    """Operation to perform. Default is "readout"."""
    test_operation: str = "readout"
    """Resonator test pulse that populates the resonator. Default is "readout"."""
    rr_depletion_time: Optional[int] = None
    """Resonator depletion time in ns. Default is the predefined depletion time."""



class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
