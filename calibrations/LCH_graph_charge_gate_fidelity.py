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
t2_detuning = 0.5
t2_max = 20000
charge_gate = linspace(-0.5, 0.5, 11)
repeat_times = len(charge_gate)

for i in range(repeat_times): 
    nodes[f"LCH_const_charge_readout_fidelity_{i}"] = library.nodes["LCH_const_charge_readout_fidelity"].copy(
            name=f"LCH_const_charge_readout_fidelity_{i}",
            multiplexed = True, 
            reset_type = "active",
            num_shots = 5000,
            charge_gate_in_v = charge_gate[i],
        )

connectivity = []
for i in range(repeat_times-1):
    connectivity.append((f"LCH_const_charge_readout_fidelity_{i}", f"LCH_const_charge_readout_fidelity_{i+1}"))

g = QualibrationGraph(
    name="LCH_const_charge_readout_fidelity",
    parameters=Parameters(),
    nodes=nodes,
    connectivity=connectivity,
    orchestrator=BasicOrchestrator(skip_failed=False),
)

g.run()
