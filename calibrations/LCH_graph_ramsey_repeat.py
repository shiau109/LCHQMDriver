# %%
from typing import List
from qualibrate.orchestration.basic_orchestrator import BasicOrchestrator
from qualibrate.parameters import GraphParameters
from qualibrate.qualibration_graph import QualibrationGraph
from qualibrate.qualibration_library import QualibrationLibrary
from typing import List, Optional, Literal

library = QualibrationLibrary.get_active_library()


class Parameters(GraphParameters):
    qubits: List[str] = None
    multiplexed: bool = True
    use_state_discrimination: bool = True

nodes = {}
t2_detuning = 0.5
t2_max = 10000
repeat_times = 10
for i in range(repeat_times): 
    nodes[f"LCH_Ramsey_{i}"] = library.nodes["LCH_Ramsey"].copy(
            name=f"LCH_Ramsey_{i}",
            multiplexed = True, 
            reset_type = "active",
            frequency_detuning_in_mhz=0.4,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns = 40000,
            wait_time_num_points = 100,
            use_state_discrimination = True,
            log_or_linear_sweep = "linear",
            num_shots = 1000,
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_Ramsey_{i}", f"LCH_Ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_ramsey_repeat",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
