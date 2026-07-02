from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """N-swap (swap-chain) circuit parameters.

    Sweeps the number of swaps and reads out the selected `qubits` (the measured set) at
    the end. Each qubit's population-vs-N curve is fit with a cosine (scqat
    SwapOscillationEstimator); there is no state writeback.
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
    swap_pair: str = "q1_q2"
    """Name of the qubit pair the SWAP is applied to each swap. Its control qubit is
    excited with x180 for state prep. Default is "q1_q2"."""
    swap_operation: str = "iswap"
    """Macro key on the swap pair (`pair.macros[swap_operation].apply()`). Must be
    invokable with no extra args. Default is "iswap"."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    """Parameter set for LCH_qc_N_swap (N-swap / swap-chain circuit).

    `qubits` (from QubitsExperimentNodeParameters) is the MEASURED set read out at the
    end of the circuit; `reset_type`/`simulate`/`timeout`/`load_data_id`/`multiplexed`
    come from CommonNodeParameters.
    """
