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
driving_list = [(0.75, 292350000.0), (0.8, 294450000.0), (0.85, 296800000.0)]

span = 0.2
repeat_times = len(driving_list)

for i in range(repeat_times): 
    driving_freq_center_mhz = driving_list[i][1]/1e6
    nodes[f"LCH_qubit_parametric_drive_freq_time_{i}"] = library.nodes["LCH_qubit_parametric_drive_freq_time"].copy(
            name=f"LCH_qubit_parametric_drive_freq_time_{i}",
            max_driving_time_ns = 8000,
            min_driving_time_ns = 40,
            driving_time_step = 16,
            max_frequency_mhz = driving_freq_center_mhz + span/2,
            min_frequency_mhz = driving_freq_center_mhz - span/2,
            frequency_points = 21,
            driving_amp_ratio = driving_list[i][0],
            use_state_discrimination = True,
            simulate = False,
            num_shots = 2000,
            multiplexed = True
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_qubit_parametric_drive_freq_time_{i}", f"LCH_qubit_parametric_drive_freq_time_{i+1}"))

g = QualibrationGraph(
    name="LCH_qubit_parametric_drive_freq_time",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q1"])

