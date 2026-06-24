from typing import Literal, Optional
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import PlottingParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    amp_mode: Literal["absolute", "prefactor"] = "prefactor"
    """How the amplitude sweep is read: "absolute" volts (emitted pulse = a V, |a/ref| < 2
    enforced, ref = the qubit z 'const' op amplitude) or unitless "prefactor"
    (amplitude_scale, the current behavior). Default "prefactor"."""
    drive_amp_min: float = 0
    """Start of the drive amplitude sweep (volts if "absolute", else prefactor). Default is 0."""
    drive_amp_max: float = 1.5
    """End of the drive amplitude sweep (volts if "absolute", else prefactor). Default is 1.5."""
    drive_amp_points: int = 51
    """Number of points in the amplitude sweep. Default is 51."""
    max_frequency_mhz: float = 300
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_mhz: float = 100
    """Minimum frequency in MHz. Default is -250 MHz."""
    frequency_points: int = 51
    """Number of frequency points. Default is 51."""
    driving_time_in_ns: int = 2000
    """Driving time in nanoseconds. Default is 2000 ns."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
