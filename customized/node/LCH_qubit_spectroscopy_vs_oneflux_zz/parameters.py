from typing import Optional

from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import CommonFluxParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 50
    """Number of averages to perform. Default is 50."""
    operation: str = "saturation"
    """Operation to perform. Default is "saturation"."""
    operation_amplitude_factor: float = 0.1
    """Amplitude factor for the operation. Default is 0.1."""
    operation_len_in_ns: Optional[int] = None
    """Length of the operation in ns. Default is the predefined pulse length."""
    max_frequency_in_mhz: float = 100.0
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_in_mhz: float = -100
    """Minimum frequency in MHz. Default is -250 MHz."""
    num_frequency_points: int = 101
    """Number of frequency points. Default is 51."""
    max_flux_amp_in_v: float = 0.05
    """Minimum flux bias offset in volts. Default is -0.02 V."""
    min_flux_amp_in_v: float = -0.05
    """Minimum flux bias offset in volts. Default is -0.02 V."""
    num_flux_points: int = 21
    """Number of flux points. Default is 51."""
    input_line_impedance_in_ohm: Optional[int] = 50
    """Input line impedance in ohms. Default is 50 Ohm."""
    line_attenuation_in_db: Optional[int] = 0
    """Line attenuation in dB. Default is 0 dB."""
    z_source_qubit: Optional[str] = "q0"
    """Z source of specific qubit. Default is "q0"."""
    xy_source_qubit: Optional[str] = "q0"
    """XY source of specific qubit. Default is "q0"."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
