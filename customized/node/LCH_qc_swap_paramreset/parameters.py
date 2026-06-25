from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """Swap-based-reset circuit parameters.

    Sweeps the number of swap+reset rounds and reads out the selected `qubits` (the
    measured set) at the end. There is no fit and no state writeback.
    """

    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    min_rounds: int = 0
    """Start of the round sweep (number of swap+reset rounds). 0 is the no-round
    baseline (just the x180 prep). Default is 0."""
    max_rounds: int = 10
    """End (inclusive) of the round sweep. Default is 10."""
    rounds_step: int = 1
    """Step of the round sweep. Default is 1."""
    swap_pair: str = "q1_q2"
    """Name of the qubit pair the SWAP is applied to each round. Its control qubit is
    excited with x180 for state prep. Default is "q1_q2"."""
    swap_operation: str = "iswap"
    """Macro key on the swap pair (`pair.macros[swap_operation].apply()`). Must be
    invokable with no extra args. Default is "iswap"."""
    reset_qubit: str = "q2"
    """Name of the ancilla qubit the RESET is applied to each round. Default is "q2"."""
    reset_operation: str = "reset"
    """Macro key on the reset qubit (`reset_qubit.macros[reset_operation].apply()`). Must
    be invokable with no extra args. Default is "reset"."""
    apply_reset: bool = True
    """Whether to apply the reset macro each round. False drops all resets, leaving pure
    swap rounds (vacuum-Rabi vs rounds) to verify the swap transfers in-context. Default True."""
    settle_ns: int = 0
    """Idle time (ns, multiple of 4) inserted on the swap pair's flux lines before each swap,
    so a preceding reset's flux pulse can settle before the narrow swap resonance. Default 0."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    """Parameter set for LCH_qc_swap_paramreset (swap-based-reset circuit).

    `qubits` (from QubitsExperimentNodeParameters) is the MEASURED set read out at the
    end of the circuit; `reset_type`/`simulate`/`timeout`/`load_data_id`/`multiplexed`
    come from CommonNodeParameters.
    """
