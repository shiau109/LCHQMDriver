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

charge_gate = linspace(-0.5, 0.5, 41)
repeat_times = len(charge_gate)

for i in range(repeat_times): 
    nodes[f"LCH_const_charge_gate_ramsey_{i}"] = library.nodes["LCH_const_charge_gate_ramsey"].copy(
            name=f"LCH_const_charge_gate_ramsey_{i}",
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns=40000,
            wait_time_num_points=100,
            use_state_discrimination = True,
            multiplexed = True, 
            log_or_linear_sweep = "linear",
            reset_type = "active",
            num_shots = 200,
            charge_gate_in_v = charge_gate[i],
        )
    nodes[f"LCH_const_charge_readout_power_{i}"] = library.nodes["LCH_const_charge_readout_power"].copy(
            name=f"LCH_const_charge_readout_power_{i}",
            multiplexed = True, 
            reset_type = "active",
            start_amp=0.9,
            end_amp=1.9,
            num_amps=11,
            num_shots = 500,
            charge_gate_in_v = charge_gate[i],
        )
connectivity = []
for i in range(repeat_times):
    connectivity.append((f"LCH_const_charge_gate_ramsey_{i}", f"LCH_const_charge_readout_power_{i}"))
    if i<repeat_times-1:
        connectivity.append((f"LCH_const_charge_readout_power_{i}", f"LCH_const_charge_gate_ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_charge_gate_ramsey_power_fidelity",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
