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
driving_list = [(0.75, 292350000.0), (0.8, 294400000.0), (0.85, 296800000.0), (0.9, 299350000.0),(0.95, 302300000.0), (1.0, 305600000.0), (1.05, 309000000.0),(1.1, 312200000.0), (1.15, 315150000.0), (1.2, 317950000.0),(1.25, 320750000.0), (1.3, 323600000.0), (1.35, 326300000.0),(1.4, 328800000.0), (1.45, 330950000.0), (1.5, 332900000.0),(1.55, 334750000.0), (1.6, 336500000.0), (1.65, 338300000.0),(1.7, 340150000.0), (1.75, 342050000.0), (1.8, 344100000.0)]


span = 0.3
repeat_times = len(driving_list)

for i in range(repeat_times): 
    driving_freq_center_mhz = driving_list[i][1]/1e6
    nodes[f"LCH_qubit_parametric_drive_time_{i}"] = library.nodes["LCH_qubit_parametric_drive_time"].copy(
            name=f"LCH_qubit_parametric_drive_time_{i}",
            max_driving_time_ns = 8000,
            min_driving_time_ns = 40,
            driving_time_step = 16,
            max_frequency_mhz = driving_freq_center_mhz + span/2,
            min_frequency_mhz = driving_freq_center_mhz - span/2,
            frequency_points = 31,
            driving_amp_ratio = driving_list[i][0],
            use_state_discrimination = True,
            simulate = False,
            num_shots = 2000,
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

g.run(qubits=["q1"])

