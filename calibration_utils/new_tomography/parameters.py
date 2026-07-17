from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from customized.common_parameters import CommonFluxParameters

from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters
from pydantic import Field


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 1000
    """Number of tomography shots. Default is 1000."""
    num_training_shots: int = 2000
    """Number of shots for GMM classifier training. Default is 2000."""
    gate_counts: list[int] = Field(
        default_factory=lambda: [0, 1, 2],
        description="Gate counts to sweep."
    )
    qubit_configs: dict[str, dict[str, str]] = Field(
        default_factory=dict,
        description="Qubit configurations mapping qubit name to init_state ('0','1','+','-','+i','-i') and target_gate ('I','X','X90','Y','Y90')"
    )
    symmetrized_readout: bool = True
    """Whether to perform symmetrized readout."""


class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
