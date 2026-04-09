# %%
from typing import List

from qualibrate.orchestration.basic_orchestrator import BasicOrchestrator
from qualibrate.parameters import GraphParameters
from qualibrate.qualibration_graph import QualibrationGraph
from qualibrate.qualibration_library import QualibrationLibrary
from typing import List, Optional, Literal
from pathlib import Path

library = QualibrationLibrary.get_active_library()#Path(r"D:\github\LCHQMDriver\calibrations"))
print(library.nodes.keys())

class Parameters(GraphParameters):
    qubits: List[str] = None
    multiplexed: bool = True
    use_state_discrimination: bool = True

nodes = {} 
repeat_times = 100

for i in range(repeat_times): 
    nodes[f"LCH_charge_gate_ramsey_{i}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{i}",
            reset_type = "active",
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns= 16,
            max_wait_time_in_ns = 80000,
            wait_time_num_points = 100,
            # use_state_discrimination = True,
            charge_gate_start_in_v = -0.48,
            charge_gate_end_in_v = 0.48,
            charge_gate_step_in_v = 0.04,
            gate_period_in_volt = 0.93,
            log_or_linear_sweep = "linear",
            num_shots = 100,
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_charge_gate_ramsey_{i}", f"LCH_charge_gate_ramsey_{i+1}"))
    # if i<repeat_times-1:
    # connectivity.append((f"LCH_charge_gate_readout_power_with_ref_{i}", f"LCH_charge_gate_ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_charge_gate_r",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q1"])
