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


repeat_times = 10

for i in range(repeat_times): 
    nodes[f"05_T1_{i}"] = library.nodes["05_T1"].copy(
            name=f"05_T1_{i}",
            reset_type = "thermal",
            multiplexed = True, 
            use_state_discrimination = True,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns=200000,
            wait_time_num_points=100,
            log_or_linear_sweep = "log",
            num_shots = 200,
        )
    nodes[f"LCH_Ramsey_{i}"] = library.nodes["LCH_Ramsey"].copy(
            name=f"LCH_Ramsey_{i}",
            reset_type = "thermal",
            multiplexed = True, 
            use_state_discrimination = True,
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns = 20000,
            wait_time_num_points = 100,
            log_or_linear_sweep = "linear",
            num_shots = 200,
        )
    nodes[f"06b_echo_{i}"] = library.nodes["06b_echo"].copy(
            name=f"06b_echo_{i}",
            reset_type = "thermal",
            multiplexed = True, 
            min_wait_time_in_ns=16,
            max_wait_time_in_ns = 200000,
            wait_time_num_points = 100,
            use_state_discrimination = True,
            log_or_linear_sweep = "log",
            num_shots = 200,
        )
    nodes[f"LCH_readout_fidelity_{i}"] = library.nodes["LCH_readout_fidelity"].copy(
            name=f"LCH_readout_fidelity_{i}",
            reset_type = "thermal",
            multiplexed = True, 
            num_shots = 10000,
        )
connectivity = []
for i in range(repeat_times):
    connectivity.append((f"05_T1_{i}", f"LCH_Ramsey_{i}"))
    connectivity.append((f"LCH_Ramsey_{i}", f"06b_echo_{i}"))
    connectivity.append((f"06b_echo_{i}", f"LCH_readout_fidelity_{i}"))
    if i<repeat_times-1:
        connectivity.append((f"LCH_readout_fidelity_{i}", f"05_T1_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_T1_T2_ROF",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
