from typing import Optional
from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    max_amp_ratio: float = 1.5
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_amp_ratio: float = 0
    """Minimum frequency in MHz. Default is -250 MHz."""
    amp_ratio_points: int = 51
    """Number of frequency points. Default is 51."""
    max_frequency_mhz: float = 300
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_mhz: float = 100
    """Minimum frequency in MHz. Default is -250 MHz."""
    frequency_points: int = 51
    """Number of frequency points. Default is 51."""
    driving_time_in_ns: int = 2000
    """Driving time in nanoseconds. Default is 2000 ns."""
    operation: str = "saturation"
    """Type of operation to perform. Default is "saturation"."""
    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on. Default is None."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
