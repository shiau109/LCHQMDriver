# %% {Imports}
from copy import deepcopy
import matplotlib.pyplot as plt
import xarray as xr
from dataclasses import asdict

from qm.qua import *

from qualang_tools.loops import from_array
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_parity_switch_ramsey import (
    Parameters,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher

import numpy as np

# %% {Description}
description = """
        Ask LCH
        Do not use multiplexing for this experiment
"""

node = QualibrationNode[Parameters, Quam](name="LCH_parity_switch_ramsey", description=description, parameters=Parameters())


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    # You can get type hinting in your IDE by typing node.parameters.
    # node.parameters.qubits = ["q1", "q2"]
    pass


## Instantiate the QUAM class from the state file
node.machine = Quam.load()


# %% {Create_QUA_program}
@node.run_action(skip_if=node.parameters.load_data_id is not None)
def create_qua_program(node: QualibrationNode[Parameters, Quam]):
    """Create the sweep axes and generate the QUA program from the pulse sequence and the node parameters."""
    # Class containing tools to help handle units and conversions.
    u = unit(coerce_to_integer=True)
    # Get the active qubits from the node and organize them by batches
    node.namespace["qubits"] = qubits = get_qubits(node)
    num_qubits = len(qubits)
    
    n_avg = node.parameters.num_shots

    flux_idle_case = node.parameters.flux_idle_case
    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "shot_idx": xr.DataArray(np.linspace(1, n_avg, n_avg), attrs={"long_name": "number of shots"}),
    }
    with program() as node.namespace["qua_program"]:
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        idle_time = declare(int)
 
        if node.parameters.use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit, flux_point=flux_idle_case)
            align()
            
            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)

                # Qubit initialization
                for i, qubit in multiplexed_qubits.items():
                    qubit.resonator.wait(qubit.resonator.depletion_time//4 * u.ns)

                align()
                # Qubit manipulation
                for i, qubit in multiplexed_qubits.items():

                    # with strict_timing_():
                    qubit.xy.play("y90")
                    if node.parameters.idle_time_in_ns is not None:
                        idle_time = node.parameters.idle_time_in_ns//4
                    else:
                        d_f = qubit.charge_dispersion
                        if d_f == 0:
                            idle_time = int(4)
                        else:
                            idle_time = int((1 /(d_f/1e9)/4)//4)
                            if idle_time > node.parameters.max_idle_time_in_ns//4:
                                idle_time = int(node.parameters.max_idle_time_in_ns//4)
                    print(f"Idle time for qubit {qubit.name}: {idle_time*4} ns")
                    qubit.xy.wait(idle_time)
                    qubit.xy.play("x90")

                align()
                for i, qubit in multiplexed_qubits.items():
                    if node.parameters.use_state_discrimination:
                        qubit.readout_state(state[i])
                        save(state[i], state_st[i])
                    else:
                        qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                        save(I[i], I_st[i])
                        save(Q[i], Q_st[i])
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                if node.parameters.use_state_discrimination:
                    state_st[i].buffer(n_avg).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(n_avg).average().save(f"I{i + 1}")
                    Q_st[i].buffer(n_avg).average().save(f"Q{i + 1}")


# %% {Simulate}
@node.run_action(skip_if=node.parameters.load_data_id is not None or not node.parameters.simulate)
def simulate_qua_program(node: QualibrationNode[Parameters, Quam]):
    """Connect to the QOP and simulate the QUA program"""
    # Connect to the QOP
    qmm = node.machine.connect()
    # Get the config from the machine
    config = node.machine.generate_config()
    # Simulate the QUA program, generate the waveform report and plot the simulated samples
    samples, fig, wf_report = simulate_and_plot(qmm, config, node.namespace["qua_program"], node.parameters)
    # Store the figure, waveform report and simulated samples
    node.results["simulation"] = {"figure": fig, "wf_report": wf_report, "samples": samples}


# %% {Execute}
@node.run_action(skip_if=node.parameters.load_data_id is not None or node.parameters.simulate)
def execute_qua_program(node: QualibrationNode[Parameters, Quam]):
    """Connect to the QOP, execute the QUA program and fetch the raw data and store it in a xarray dataset called "ds_raw"."""
    # Connect to the QOP
    qmm = node.machine.connect()
    # Get the config from the machine
    config = node.machine.generate_config()
    # Execute the QUA program only if the quantum machine is available (this is to avoid interrupting running jobs).
    with qm_session(qmm, config, timeout=node.parameters.timeout) as qm:
        # The job is stored in the node namespace to be reused in the fetching_data run_action
        node.namespace["job"] = job = qm.execute(node.namespace["qua_program"])
        # Display the progress bar
        data_fetcher = XarrayDataFetcher(job, node.namespace["sweep_axes"])
        for dataset in data_fetcher:
            progress_counter(
                data_fetcher["n"],
                node.parameters.num_shots,
                start_time=data_fetcher.t_start,
            )
        # Display the execution report to expose possible runtime errors
        node.log(job.execution_report())
    # Register the raw dataset
    node.results["ds_raw"] = dataset


# %% {Load_historical_data}
@node.run_action(skip_if=node.parameters.load_data_id is None)
def load_data(node: QualibrationNode[Parameters, Quam]):
    """Load a previously acquired dataset."""
    load_data_id = node.parameters.load_data_id
    # Load the specified dataset
    node.load_from_id(node.parameters.load_data_id)
    node.parameters.load_data_id = load_data_id
    # Get the active qubits from the loaded node parameters
    node.namespace["qubits"] = get_qubits(node)


# %% {Analyse_data}
@node.run_action(skip_if=node.parameters.simulate)
def analyse_data(node: QualibrationNode[Parameters, Quam]):
    """Analyse the raw data and store the fitted data in another xarray dataset "ds_fit" and the fitted results in the "fit_results" dictionary."""
    pass


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Plot the raw and fitted data in specific figures whose shape is given by qubit.grid_location."""
    node.results["figures"] = {}
    pass
    # for key, value in node.results["fit_results"].items():    

    #     node.results["fit_results"][key]=value.fit_result.best_values
    # # # Store the generated figures
    #     node.results["figures"][key] = value._plot_results()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    pass
    # detuning = int(node.parameters.frequency_detuning_in_mhz * 1e6)
    # with node.record_state_updates():
    #     for q in node.namespace["qubits"]:
    #         a_2 = float(node.results["fit_results"][q.name]["a_2"])
    #         f_1 = float(node.results["fit_results"][q.name]["f_1"])*1e9
    #         if a_2 == 0:
    #             d_f_01 = int(f_1)-detuning
    #             q.charge_dispersion = 0
    #         else:
    #             f_2 = float(node.results["fit_results"][q.name]["f_2"])*1e9
    #             d_f_01 = int((f_1 + f_2) / 2) -detuning
    #             q.charge_dispersion =int(abs(f_1 - f_2) / 2)
    #         q.f_01 -= d_f_01
    #         q.xy.RF_frequency -= d_f_01

# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
