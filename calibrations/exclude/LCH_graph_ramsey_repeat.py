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
    multiplexed: bool = False
    use_state_discrimination: bool = False

nodes = {}
t2_detuning = 0.2
t2_max = 40000
repeat_times = 100
for i in range(repeat_times): 
    nodes[f"ramsey_{i}"] = library.nodes["LCH_Ramsey"].copy(
            name=f"ramsey_{i}",
            frequency_detuning_in_mhz=t2_detuning,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns=t2_max,
            wait_time_num_points=64,
            use_state_discrimination = True,
            log_or_linear_sweep = "linear",
            num_shots = 256
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"ramsey_{i}", f"ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_ramsey_repeat",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
