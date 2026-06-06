# %%
from typing import List

from qualibrate.orchestration.basic_orchestrator import BasicOrchestrator
from qualibrate.core.parameters import GraphParameters
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
# pulse_name_list = ["readout_three_step", 
#                    "readout_three_step_120",
#                    "readout_three_step_160",
#                    "readout_three_step_200",
#                    "readout_three_step_240",
#                    "readout_three_step_300",
#                    "readout_three_step_340",
#                    "readout_three_step_400",
#                    "readout_three_step_500", 
#                    "readout_three_step_600", 
#                    "readout_three_step_800",
#                    "readout_three_step_1000", 
#                    "readout_three_step_1200", 
#                    "readout_square"]
pulse_name_list = ["readout_three_step", 
                   "readout_three_step_200",
                   "readout_three_step_400",
                   "readout_three_step_1000", 
                   "readout_square"]
repeat_times = 50
for i in range(repeat_times):
    for j, pulse_name in enumerate(pulse_name_list): 
        nodes[f"LCH_charge_gate_ramsey_{i}_{j}"] = library.nodes["LCH_charge_gate_ramsey"].copy(
                name=f"LCH_charge_gate_ramsey_{i}_{j}",
                reset_type = "active",
                frequency_detuning_in_mhz=0.2,
                min_wait_time_in_ns= 16,
                max_wait_time_in_ns = 60000,
                wait_time_num_points = 60,
                # use_state_discrimination = True,
                charge_gate_start_in_v = -0.45,
                charge_gate_end_in_v = 0.45,
                charge_gate_step_in_v = 0.15,
                # gate_period_in_volt = 0.85, # Q2 
                gate_period_in_volt = 0.93, # Q1 
                log_or_linear_sweep = "linear",
                num_shots = 100,
            )
        nodes[f"LCH_charge_gate_readout_power_with_ref_{i}_{pulse_name}"] = library.nodes["LCH_charge_gate_readout_power_with_ref"].copy(
                name=f"LCH_charge_gate_readout_power_with_ref_{i}_{pulse_name}",
                reset_type = "thermal",
                start_amp = 1.3,
                end_amp = 1.3,
                num_amps = 1,
                charge_gate_start_in_v = 0.08, #0.34,
                charge_gate_end_in_v = 0.08, #Q1
                # charge_gate_end_in_v = 0.480, #Q2

                charge_gate_step_in_v = 0.005,
                prepared_states = [0],
                num_shots = 4000,
                ref_operation = "readout",
                test_operation = pulse_name,
                # add_charge_offset = True,
            )
nodes[f"LCH_charge_gate_ramsey_{repeat_times}_0"] = library.nodes["LCH_charge_gate_ramsey"].copy(
            name=f"LCH_charge_gate_ramsey_{repeat_times}_0",
            reset_type = "active",
            frequency_detuning_in_mhz=0.2,
            min_wait_time_in_ns= 16,
            max_wait_time_in_ns = 60000,
            wait_time_num_points = 60,
            # use_state_discrimination = True,
            charge_gate_start_in_v = -0.45,
            charge_gate_end_in_v = 0.45,
            charge_gate_step_in_v = 0.15,
            # gate_period_in_volt = 0.85, # Q2 
            gate_period_in_volt = 0.93, # Q1 
            log_or_linear_sweep = "linear",
            num_shots = 100,
        )
connectivity = []
for i in range(repeat_times):
    for j, pulse_name in enumerate(pulse_name_list):
        connectivity.append((f"LCH_charge_gate_ramsey_{i}_{j}", f"LCH_charge_gate_readout_power_with_ref_{i}_{pulse_name}"))
        # if i<repeat_times-1:
        if j < len(pulse_name_list) - 1:
            connectivity.append((f"LCH_charge_gate_readout_power_with_ref_{i}_{pulse_name}", f"LCH_charge_gate_ramsey_{i}_{j+1}"))
        else:
            connectivity.append((f"LCH_charge_gate_readout_power_with_ref_{i}_{pulse_name}", f"LCH_charge_gate_ramsey_{i+1}_0"))


g = QualibrationGraph(
    name="LCH_graph_charge_gate_r_rp_ref_mwf",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run(qubits=["q1"])
