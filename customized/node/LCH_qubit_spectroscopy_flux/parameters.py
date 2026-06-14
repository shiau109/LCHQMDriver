from typing import Optional

from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from customized.common_parameters import PlottingParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 50
    """Number of averages to perform. Default is 50."""
    operation: str = "saturation"
    """Operation to perform. Default is "saturation"."""
    operation_amplitude_factor: float = 0.05
    """Amplitude factor for the operation. Default is 0.1."""
    operation_len_in_ns: Optional[int] = None
    """Length of the operation in ns. Default is the predefined pulse length."""
    max_frequency_in_mhz: float = 50.0
    """Maximum drive detuning in MHz. Default is 100 MHz."""
    min_frequency_in_mhz: float = -150.0
    """Minimum drive detuning in MHz. Default is -100 MHz."""
    num_frequency_points: int = 101
    """Number of frequency points. Default is 101."""
    max_flux_amp_in_v: float = 0.05
    """Maximum flux bias amplitude in volts. Default is 0.05 V."""
    min_flux_amp_in_v: float = -0.05
    """Minimum flux bias amplitude in volts. Default is -0.05 V."""
    num_flux_points: int = 21
    """Number of flux points. Default is 21."""
    z_source_qubit: Optional[str] = None
    """Name of the single qubit whose z-line drives the flux sweep. When None,
    every measured qubit applies the flux to its own z-line (same as 03b).
    Default is None."""
    xy_source_qubit: Optional[str] = None
    """Name of the single qubit whose xy-line plays the saturation drive. When
    None, every measured qubit drives its own xy-line (same as 03b). Default is None."""
    peak_prominence: float = 0.2
    """Relative prominence threshold for per-slice peak detection (fraction of the
    baseline-subtracted signal span). Lower keeps weaker peaks. Default is 0.1."""
    max_peaks_per_flux: Optional[int] = None
    """Maximum number of peaks kept per flux slice. None keeps every peak above the
    prominence threshold (recommended when the number of transitions varies)."""
    outlier_n_sigma: float = float("inf")
    """Robust-sigma threshold for rejecting detected peaks whose fitted width or
    amplitude are outliers (pooled across all peaks) before the downstream fit.
    Default is inf (no outlier rejection); lower the value to enable filtering."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    pass
