"""Parameters for the LCH_pair_qcq_zz_coupler_freq calibration node.

Measures residual ZZ coupling on a qubit-coupler-qubit (QCQ) pair as a function of the
coupler frequency. The coupler has no RF-frequency field; its frequency is tuned via the
gated ``const`` flux-pulse amplitude (volts), so the swept quantity here is that coupler
pulse amplitude.
"""

from typing import ClassVar, Literal

from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import CommonNodeParameters, QubitPairExperimentNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """Parameters specific to the LCH_pair_qcq_zz_coupler_freq calibration."""

    num_shots: int = 100
    """Number of shots to perform. Default is 100."""
    amp_min: float = -0.1
    """Minimum coupler bias amplitude (tunes coupler frequency) for the scan, in volts. Default is -0.1."""
    amp_max: float = 0.1
    """Maximum coupler bias amplitude (tunes coupler frequency) for the scan, in volts. Default is 0.1."""
    amp_step: float = 0.01
    """Step size for the coupler bias amplitude scan, in volts. Default is 0.01."""
    time_min_in_ns: float = 16
    """Minimum interaction time in nanoseconds. Default is 16."""
    time_max_in_ns: float = 8000
    """Maximum interaction time in nanoseconds. Default is 8000."""
    time_step_in_ns: float = 160
    """Step size for the interaction-time sweep in nanoseconds. Default is 160."""
    virtual_detuning_in_mhz: float = 1.0
    """Virtual detuning applied during the Hahn-echo sequence in MHz. Default is 1.0."""
    use_state_discrimination: bool = True
    """Whether to use state discrimination for readout. Default is True."""
    measure_qubit: Literal["control", "target"] = "target"
    """Which qubit in the pair to measure: 'control' or 'target'. Default is 'target'."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitPairExperimentNodeParameters,
):
    """Combined parameters for the LCH_pair_qcq_zz_coupler_freq calibration node."""

    targets_name: ClassVar[str] = "qubit_pairs"
