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

driving_amp_ratios = linspace(0.2, 1, 17)
repeat_times = len(driving_amp_ratios)

for i in range(repeat_times): 
    nodes[f"LCH_qubit_parametric_drive_time_{i}"] = library.nodes["LCH_qubit_parametric_drive_time"].copy(
            name=f"LCH_qubit_parametric_drive_time_{i}",
            max_driving_time_ns = 60000,
            min_driving_time_ns = 16,
            driving_time_step = 400,
            max_frequency_mhz = 238,
            min_frequency_mhz = 231,
            frequency_points = 141,
            driving_amp_ratio = driving_amp_ratios[i],
            use_state_discrimination = True,
            simulate = False,
            num_shots = 1000,
            multiplexed = True
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_qubit_parametric_drive_time_{i}", f"LCH_qubit_parametric_drive_time_{i+1}"))

g = QualibrationGraph(
    name="LCH_qubit_parametric_drive_time",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q2"])

