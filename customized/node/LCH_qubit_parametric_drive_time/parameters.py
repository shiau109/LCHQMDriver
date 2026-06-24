from typing import Literal, Optional
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import PlottingParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    max_driving_time_ns: int = 1000
    """Maximum driving time in nanoseconds. Default is 1000 ns."""
    min_driving_time_ns: int = 0
    """Minimum driving time in nanoseconds. Default is 0 ns."""
    driving_time_step: int = 40
    """Step size for driving time in nanoseconds. Default is 40 ns."""
    operation: str = "saturation"
    """Type of operation to perform. Default is "saturation"."""
    drive_qubit: Optional[str] = None
    """Qubit to apply the drive pulse on. Default is None."""
    max_frequency_mhz : float = 300
    """Maximum frequency in MHz. Default is 300 MHz."""
    min_frequency_mhz : float = 10
    """Minimum frequency in MHz. Default is 10 MHz."""
    frequency_points: int = 51
    """Number of frequency points to sample. Default is 51."""
    amp_mode: Literal["absolute", "prefactor"] = "prefactor"
    """How drive_amp is read: "absolute" volts (emitted pulse = drive_amp V,
    |a/ref| < 2 enforced, ref = the qubit z 'const' op amplitude) or unitless "prefactor"
    (amplitude_scale, the current behavior). Default "prefactor"."""
    drive_amp: float = 1.0
    """Fixed drive amplitude (volts if amp_mode == "absolute", else prefactor). Default is 1.0."""
    tomography: bool = False
    """If True, read out in the X/Y/Z bases for full single-qubit state tomography
    (density-matrix reconstruction). If False, read out the excited-state population
    only (rho_11). Default is False."""
    prepare_state: str = "x180"
    """State-preparation pulse played before the parametric drive. Default "x180"
    (prepare |1>); use a superposition (e.g. "x90" / "-x90") when tomography is on."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
