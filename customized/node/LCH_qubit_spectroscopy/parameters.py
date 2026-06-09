from typing import Optional
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import PlottingParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    max_frequency_in_mhz: float = 100.0
    """Maximum frequency in MHz. Default is 50 MHz."""
    min_frequency_in_mhz: float = -100
    """Minimum frequency in MHz. Default is -250 MHz."""
    num_frequency_points: int = 101
    """Number of frequency points. Default is 51."""
    operation: str = "saturation"
    """Type of operation to perform. Default is "saturation"."""
    operation_amplitude_factor: float = 1.0
    """Amplitude pre-factor for the operation. Default is 1.0."""
    operation_len_in_ns: Optional[int] = None
    """Length of the operation in nanoseconds. Default is the predefined pulse length."""
    target_peak_width: float = 3e6
    """Target peak width in Hz. Default is 3e6 Hz."""
    update_pulses_amplitude: bool = False
    """Whether to update the saturation pulse and x180/x90 pulse amplitudes based on the peak width. Default is False"""
    max_peaks: Optional[int] = 4
    """Maximum number of spectroscopy peaks the estimator keeps (most-prominent first).
    The SNR gate still rejects noise, so fewer are returned when fewer lines are real;
    set None to keep all. The peak driving the write-back is the one with the largest
    Lorentzian area. Default 4."""
    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on. Default is None."""
    save_plot_data: bool = False
    """Persist the scqat plot-data reconstruction artifact (per qubit) so figures can be
    replotted later with NO re-fit. Default False to save space — it is re-derivable from
    ds_raw. (Promote to common_parameters.PlottingParameters when other nodes adopt it.)"""

class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
