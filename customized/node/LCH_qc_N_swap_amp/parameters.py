from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """N-swap (swap-chain) x qubit-flux-amplitude 2D parameters.

    Sweeps the number of swaps (inner axis) AND the swap macro's control-qubit flux
    amplitude (outer axis, absolute volts via the macro's `ctrl_amp` -- the same knob
    LCH_pair_qcq_fixed_time sweeps in swap_via_macro mode). The selected `qubits` (the
    measured set) are read out at the end; each qubit's population-vs-N curve at every
    amplitude is fit with a cosine (scqat SwapOscillationEstimator), giving the swap
    frequency versus amplitude. There is no state writeback.
    """

    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    min_rounds: int = 0
    """Start of the swap sweep (number of swaps). 0 is the no-swap baseline (just the x180
    prep). Default is 0."""
    max_rounds: int = 10
    """End (inclusive) of the swap sweep. Default is 10."""
    rounds_step: int = 1
    """Step of the swap sweep. Default is 1."""
    qubit_amp_start: float = -0.1
    """Start of the control-qubit flux amplitude sweep, in absolute volts (the macro's
    ctrl_amp rescales its z flux pulse to this value). Default is -0.1."""
    qubit_amp_end: float = 0.1
    """End (exclusive) of the control-qubit flux amplitude sweep. Default is 0.1."""
    qubit_amp_step: float = 0.01
    """Step of the control-qubit flux amplitude sweep. Default is 0.01."""
    swap_pair: str = "q1_q2"
    """Name of the qubit pair the SWAP is applied to each swap. Its control qubit is
    excited with x180 for state prep. Default is "q1_q2"."""
    swap_operation: str = "iswap"
    """Macro key on the swap pair (`pair.macros[swap_operation].apply(ctrl_amp=...)`).
    Must expose a z `flux_pulse` and accept ctrl_amp. Default is "iswap"."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    """Parameter set for LCH_qc_N_swap_amp (N-swap x qubit-flux-amplitude 2D sweep).

    `qubits` (from QubitsExperimentNodeParameters) is the MEASURED set read out at the
    end of the circuit; `reset_type`/`simulate`/`timeout`/`load_data_id`/`multiplexed`
    come from CommonNodeParameters.
    """
