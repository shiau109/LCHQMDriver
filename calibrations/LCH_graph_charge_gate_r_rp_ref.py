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
repeat_times = 20

for i in range(repeat_times): 
    nodes[f"LCH_charge_gate_ramsey_{i}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{i}",
            reset_type = "thermal",
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns= 16,
            max_wait_time_in_ns = 60000,
            wait_time_num_points = 60,
            # use_state_discrimination = True,
            charge_gate_start_in_v = -0.45,
            charge_gate_end_in_v = 0.45,
            charge_gate_step_in_v = 0.18,
            log_or_linear_sweep = "linear",
            num_shots = 50,
        )
    nodes[f"LCH_charge_gate_readout_power_ref_{i}"] = library.nodes["LCH_charge_gate_readout_power_ref"].copy(
            name=f"LCH_charge_gate_readout_power_ref_{i}",
            reset_type = "thermal",
            start_amp = 0,
            end_amp = 1.8,
            num_amps = 10,
            charge_gate_start_in_v = 0,
            charge_gate_end_in_v = 0.480,
            charge_gate_step_in_v = 0.005,
            prepared_states = [0,1],
            num_shots = 10,
            ref_operation = "readout",
            test_operation = "ts_readout",
            # add_charge_offset = True,
        )
nodes[f"LCH_charge_gate_ramsey_{repeat_times}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{repeat_times}",
            reset_type = "thermal",
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns= 16,
            max_wait_time_in_ns = 60000,
            wait_time_num_points = 60,
            # use_state_discrimination = True,
            charge_gate_start_in_v = -0.45,
            charge_gate_end_in_v = 0.45,
            charge_gate_step_in_v = 0.18,
            log_or_linear_sweep = "linear",
            num_shots = 50,
        )
connectivity = []
for i in range(repeat_times):
    connectivity.append((f"LCH_charge_gate_ramsey_{i}", f"LCH_charge_gate_readout_power_ref_{i}"))
    # if i<repeat_times-1:
    connectivity.append((f"LCH_charge_gate_readout_power_ref_{i}", f"LCH_charge_gate_ramsey_{i+1}"))

g = QualibrationGraph(
    name="LCH_graph_charge_gate_r_rp_ref",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    # orchestrator=BasicOrchestrator(skip_failed=False),
)

# g.run(qubits=["q1"])
