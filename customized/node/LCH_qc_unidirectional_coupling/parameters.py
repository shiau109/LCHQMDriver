from typing import List, Optional

from customized.common_parameters import PlottingParameters
from qualibrate import NodeParameters
from qualibrate.core.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    """Unidirectional-coupling circuit parameters.

    Sweeps the number of (swap-chain)+reset rounds and reads out the selected `qubits` (the
    measured set) at the end. Each round applies an ordered chain of SWAPs (one per pair in
    `swap_pairs`, in list order) then a RESET. There is no fit and no state writeback.
    """

    num_shots: int = 100
    """Number of averages to perform. Default is 100."""
    min_rounds: int = 0
    """Start of the round sweep (number of (swap-chain)+reset rounds). 0 is the no-round
    baseline (just the x180 prep). Default is 0."""
    max_rounds: int = 10
    """End (inclusive) of the round sweep. Default is 10."""
    rounds_step: int = 1
    """Step of the round sweep. Default is 1."""
    excite_qubit: Optional[str] = None
    """Name of the qubit excited with x180 for state prep at the start of each shot.
    Required — must be set explicitly (no default); e.g. "q3". (None is only a sentinel so
    `Parameters()` instantiates for the GUI; the shell rejects an unset value at run time.)"""
    swap_pairs: List[str] = ["q1_q2", "q2_q3"]
    """Ordered list of qubit-pair names whose SWAP macros are applied in sequence each round
    (e.g. ["q1_q2","q2_q3"] swaps q1_q2 first, then q2_q3 — the unidirectional chain). Each
    pair must carry a bare-callable `swap_operation` macro. Default ["q1_q2","q2_q3"]."""
    swap_operation: str = "iswap"
    """Macro key applied on every pair in `swap_pairs` (`pair.macros[swap_operation].apply()`).
    Must be invokable with no extra args. Default is "iswap"."""
    reset_qubit: str = "q2"
    """Name of the ancilla qubit the RESET is applied to each round. Default is "q2"."""
    reset_operation: str = "reset"
    """Macro key on the reset qubit (`reset_qubit.macros[reset_operation].apply()`). Must
    be invokable with no extra args. Default is "reset"."""
    settle_ns: int = 0
    """Idle time (ns, multiple of 4) inserted on each swap pair's flux lines before its swap,
    so a preceding flux pulse can settle before the narrow swap resonance. Default 0."""
    use_state_discrimination: bool = True
    """Whether to read out qubit state (True) or raw I/Q (False). Default is True."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    PlottingParameters,
):
    """Parameter set for LCH_qc_unidirectional_coupling (unidirectional swap-chain circuit).

    `qubits` (from QubitsExperimentNodeParameters) is the MEASURED set read out at the
    end of the circuit; `reset_type`/`simulate`/`timeout`/`load_data_id`/`multiplexed`
    come from CommonNodeParameters.
    """
