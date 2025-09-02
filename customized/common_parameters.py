from typing import Optional
from qualibrate.parameters import RunnableParameters
from quam_builder.architecture.superconducting.qpu import AnyQuam
from quam_builder.architecture.superconducting.qubit import AnyTransmon
from quam_builder.architecture.superconducting.qubit_pair import AnyTransmonPair
from typing import List, Optional, Literal
# from quam.components.quantum_components import qubit_pair
from qualibration_libs.core import BatchableList
from qualibrate import QualibrationNode


class CommonFluxParameters(RunnableParameters):
    """Common parameters for configuring a flux control node in a quantum machine simulation or execution."""

    flux_idle_case: str = "joint"
    """Flux point to control. Default is 'joint'."""



class QubitPairsExperimentNodeParameters(RunnableParameters):
    """Common parameters for configuring a 2-qubit experiment in a quantum machine simulation or execution."""

    qubit_pair: Optional[List[str]] = None
    """a qubit pair. Default is 'q0-1'."""


def get_qubit_pairs(node: QualibrationNode) -> List[AnyTransmonPair]:
    qubit_pairs = _get_qubit_pairs(node.machine, node.parameters)

    return qubit_pairs

def _get_qubit_pairs(
    machine: AnyQuam, node_parameters: QubitPairsExperimentNodeParameters
) -> List[AnyTransmonPair]:
    if node_parameters.qubit_pair is None or node_parameters.qubit_pair == "":
        qubit_pairs = machine.active_qubit_pairs
    else:
        qubit_pairs = [machine.qubit_pairs[q] for q in node_parameters.qubit_pair]

    return qubit_pairs
