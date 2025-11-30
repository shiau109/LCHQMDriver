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
repeat_times = 21

for i in range(repeat_times): 
    nodes[f"LCH_charge_gate_ramsey_{i}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{i}",
            reset_type = "active",
            frequency_detuning_in_mhz=0.25,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns = 80000,
            wait_time_num_points = 100,
            use_state_discrimination = True,
            charge_gate_start_in_v = -0.5,
            charge_gate_end_in_v = 0.5,
            charge_gate_step_in_v = 0.1,
            log_or_linear_sweep = "linear",
            num_shots = 200,
        )
    nodes[f"LCH_charge_gate_readout_power_{i}"] = library.nodes["LCH_charge_gate_readout_power"].copy(
            name=f"LCH_charge_gate_readout_power_{i}",
            reset_type = "active",
            start_amp = 0.2,
            end_amp = 1.9,
            num_amps = 35,
            charge_gate_start_in_v = -0.5,
            charge_gate_end_in_v = 0.5,
            charge_gate_step_in_v = 0.005,
            prepared_states = [1],
            num_shots = 100,
        )
nodes[f"LCH_charge_gate_ramsey_{repeat_times}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{repeat_times}",
            reset_type = "active",
            frequency_detuning_in_mhz=0.25,
            min_wait_time_in_ns=16,
            max_wait_time_in_ns = 80000,
            wait_time_num_points = 100,
            use_state_discrimination = True,
            charge_gate_start_in_v = -0.5,
            charge_gate_end_in_v = 0.5,
            charge_gate_step_in_v = 0.1,
            log_or_linear_sweep = "linear",
            num_shots = 200,
        )
connectivity = []
for i in range(repeat_times):
    connectivity.append((f"LCH_charge_gate_ramsey_{i}", f"LCH_charge_gate_readout_power_{i}"))
    # if i<repeat_times-1:
    connectivity.append((f"LCH_charge_gate_readout_power_{i}", f"LCH_charge_gate_ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_charge_gate_r_rp",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q1"])
