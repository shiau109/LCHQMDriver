from typing import Optional
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import PlottingParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    min_flux_offset_in_v: float = -0.5
    """Minimum flux bias offset in volts. Default is -0.5 V."""
    max_flux_offset_in_v: float = 0.5
    """Maximum flux bias offset in volts. Default is 0.5 V."""
    num_flux_points: int = 21
    """Number of flux points. Default is 21."""
    frequency_span_in_mhz: float = 15
    """Frequency span in MHz. Default is 15 MHz."""
    frequency_step_in_mhz: float = 0.1
    """Frequency step in MHz. Default is 0.1 MHz."""
    input_line_impedance_in_ohm: float = 50
    """Input line impedance in ohms. Default is 50 Ohm."""
    line_attenuation_in_db: float = 0
    """Line attenuation in dB. Default is 0 dB."""
    update_flux_min: bool = False
    """Flag to update flux minimum frequency point. Default is False."""
    outlier_n_sigma: float = 3.0
    """Robust-sigma threshold for rejecting flux points whose fitted dip width or
    amplitude are outliers before the frequency-vs-flux fit. Default is 3.0."""
    z_source_qubit: Optional[str] = None
    """Name of the single qubit whose z-line drives the flux sweep. When None,
    every measured qubit applies the flux to its own z-line (same as the official
    02c node). Default is None."""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
