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

prepare = [ "y90", "-y90", "-x90", "x90", "I", "x180"]
labels = ["xp", "xm", "yp", "ym", "zp", "zm"]
for i in range(len(prepare) ): 
    nodes[f"LCH_temporal_steering_{labels[i]}"] = library.nodes["LCH_temporal_steering"].copy(
            name=f"LCH_temporal_steering_{labels[i]}",
            multiplexed = False, 
            qubits = ["q0"],
            reset_type = "active",
            use_state_discrimination = True,
            num_shots = 10000,
            prepare_gate = prepare[i],
            min_wait_time_in_ns = 16,
            max_wait_time_in_ns = 32000,
            wait_time_num_points = 100,
            log_or_linear_sweep= "linear",
            )

connectivity = []
for i in range(len(prepare)-1):
    connectivity.append((f"LCH_temporal_steering_{labels[i]}", f"LCH_temporal_steering_{labels[i+1]}"))

g = QualibrationGraph(
    name="LCH_temporal_steering",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()

# %%
