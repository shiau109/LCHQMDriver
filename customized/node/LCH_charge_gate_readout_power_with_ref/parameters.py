from qualibrate import NodeParameters
from qualibrate.parameters import RunnableParameters
from qualibration_libs.parameters import QubitsExperimentNodeParameters, CommonNodeParameters


class NodeSpecificParameters(RunnableParameters):
    num_shots: int = 50
    """Number of shots to perform. Default is 2000."""
    start_amp: float = 0
    """Start amplitude. Default is 0.5."""
    end_amp: float = 1.5
    """End amplitude. Default is 1.99."""
    num_amps: int = 2
    """Number of amplitudes to sweep. Default is 10."""
    charge_gate_start_in_v: float = -0.5
    """Charge gate voltage in V. Default is -0.5 V."""
    charge_gate_end_in_v: float = 0.5
    """Charge gate voltage in V. Default is 0.5 V."""
    charge_gate_step_in_v: float = 0.5
    """Charge gate voltage in V. Default is 0.05 V."""
    prepared_states: list[int] = [0]
    """List of prepared states. Default is [0]."""
    ref_operation: str = "readout"
    """Type of operation to perform for the reference point. Default is "readout"."""
    test_operation: str = "ts_readout"
    """Type of operation to perform for the test point. Default is "readout"."""
    
class Parameters(
    NodeParameters,
    CommonNodeParameters,
    NodeSpecificParameters,
    QubitsExperimentNodeParameters,
):
    pass
