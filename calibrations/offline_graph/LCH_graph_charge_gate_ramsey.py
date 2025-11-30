# %%
from typing import List
from qualibrate.orchestration.basic_orchestrator import BasicOrchestrator
from qualibrate.parameters import GraphParameters
from qualibrate.qualibration_graph import QualibrationGraph
from qualibrate.qualibration_library import QualibrationLibrary
from typing import List, Optional, Literal
from numpy import linspace
library = QualibrationLibrary.get_active_library()


class Parameters(GraphParameters):
    qubits: List[str] = None
    multiplexed: bool = True
    use_state_discrimination: bool = True

nodes = {}
t2_detuning = 0.25
t2_max = 80000
charge_gate = linspace(-0.5, 0.5, 21)
repeat_times = len(charge_gate)

for i in range(repeat_times): 
    nodes[f"LCH_const_charge_gate_ramsey_{i}"] = library.nodes["LCH_const_charge_gate_ramsey"].copy(
            name=f"LCH_const_charge_gate_ramsey_{i}",
            frequency_detuning_in_mhz=t2_detuning,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns=t2_max,
            wait_time_num_points=100,
            use_state_discrimination = True,
            multiplexed = True, 
            log_or_linear_sweep = "linear",
            reset_type = "thermal",
            num_shots = 200,
            charge_gate_in_v = charge_gate[i],
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_const_charge_gate_ramsey_{i}", f"LCH_const_charge_gate_ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_const_charge_gate_ramsey",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q1"])

