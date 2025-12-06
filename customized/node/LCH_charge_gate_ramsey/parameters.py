from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from customized.common_parameters import CommonFluxParameters
from typing import Optional
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters, IdleTimeNodeParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 200
    """Number of averages to perform. Default is 100."""
    frequency_detuning_in_mhz: float = 0.25
    """Frequency detuning in MHz. Default is 0.25 MHz."""
    charge_gate_start_in_v: float = -0.5
    """Charge gate voltage in V. Default is -0.1 V."""
    charge_gate_end_in_v: float = 0.5
    """Charge gate voltage in V. Default is 0.1 V."""
    charge_gate_step_in_v: float = 0.05
    """Charge gate voltage in V. Default is 0.1 V."""
    gate_period_in_volt: Optional[float] = 0.9174
    """Gate period (min/max to min/max), in Volt. Default is 0.9174 V."""
class Parameters(
    NodeParameters,
    CommonNodeParameters,
    IdleTimeNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
    CommonFluxParameters,
):
    pass
