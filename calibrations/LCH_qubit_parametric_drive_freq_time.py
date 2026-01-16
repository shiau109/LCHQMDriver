# %% {Imports}
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from dataclasses import asdict

from qm.qua import *

from qualang_tools.loops import from_array
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_qubit_parametric_drive_time import Parameters
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Node initialisation}
description = """
        Ask LCH
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_qubit_parametric_drive_time",  # Name should be unique
    description=description,  # Describe what the node is doing, which is also reflected in the QUAlibrate GUI
    parameters=Parameters(),  # Node parameters defined under quam_experiment/experiments/node_name
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    # You can get type hinting in your IDE by typing node.parameters.
    node.parameters.qubits = ["q2"]
    node.parameters.max_driving_time_ns = 50000
    node.parameters.min_driving_time_ns = 16
    node.parameters.driving_time_step = 1000
    node.parameters.max_frequency_mhz = 300
    node.parameters.min_frequency_mhz = 10
    node.parameters.frequency_points = 51
    node.parameters.use_state_discrimination = True
    node.parameters.simulate = True
    node.parameters.num_shots = 1000
    node.parameters.multiplexed = True
    pass


# Instantiate the QUAM class from the state file
node.machine = Quam.load()


# %% {Create_QUA_program}
@node.run_action(skip_if=node.parameters.load_data_id is not None)
def create_qua_program(node: QualibrationNode[Parameters, Quam]):
    """Create the sweep axes and generate the QUA program from the pulse sequence and the node parameters."""
    # Class containing tools to help handle units and conversions.
    u = unit(coerce_to_integer=True)
    # Get the active qubits from the node and organize them by batches
    node.namespace["qubits"] = qubits = get_qubits(node)
    p = node.parameters
    num_qubits = len(qubits)

    n_avg = node.parameters.num_shots  # The number of averages

    # Qubit detuning sweep with respect to their resonance frequencies
    time_tick = np.arange(p.min_driving_time_ns//4, p.max_driving_time_ns//4, p.driving_time_step//4)
    time_ns =  time_tick*4  # in ns

    freqs = np.linspace( p.min_frequency_mhz*u.MHz, p.max_frequency_mhz*u.MHz, p.frequency_points)

    flux_idle_case = node.parameters.flux_idle_case
    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "driving_frequency": xr.DataArray(freqs, attrs={"long_name": "driving frequency", "units": "Hz"}),
        "driving_time": xr.DataArray(time_ns, attrs={"long_name": "readout frequency", "units": "Hz"}),
    }

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        tt = declare(int)  # QUA variable for the qubit frequency
        f_drive = declare(int)  # QUA variable for the qubit frequency

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
                with for_(*from_array(f_drive, freqs)): 

                    with for_(*from_array(tt, time_tick)):                        
                        for i, qubit in multiplexed_qubits.items():
                            qubit.reset(
                                node.parameters.reset_type,
                                node.parameters.simulate,
                                log_callable=node.log,
                            )

                            # Update the qubit frequency
                            qubit.z.update_frequency(f_drive)
                        
                        for i, qubit in multiplexed_qubits.items():
                            # if i == 0:                        
                            qubit.xy.play("x180")
                        align()
                        wait( (32*u.ns)//4)
                        for i, qubit in multiplexed_qubits.items():
                            if i == 0:                   
                                qubit.z.play("param", truncate=tt)
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
                    state_st[i].buffer(len(time_tick)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(time_tick)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(time_tick)).average().save(f"Q{i + 1}")


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
                data_fetcher.get("n", 0),
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
    # from qcat.parser.qm_reader import repetition_data
    # if node.parameters.use_state_discrimination:
    #     ds = node.results["ds_raw"].rename({"state": "signal"})
    # else:
    #     ds = node.results["ds_raw"].rename({"I": "signal"}) 


    # sep_data = repetition_data(ds, repetition_dim="qubit")
    # node.results["fit_results"] = {}
    # for sq_data in sep_data:
    #     qubit_name = sq_data["qubit"].values.item()
    #     print(qubit_name)
    pass

# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    from qcat.parser.qm_reader import repetition_data
    if node.parameters.use_state_discrimination:
        ds = node.results["ds_raw"].rename({"state": "signal"})
    else:
        ds = node.results["ds_raw"].rename({"I": "signal"}) 
    sep_data = repetition_data(ds, repetition_dim="qubit")

    node.results["fit_results"] = {}
    fig, ax = plt.subplots()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        ax.scatter(sq_data.detuning, sq_data.signal, label=qubit_name)
    ax.set_xlabel("Detuning")
    ax.set_ylabel("Signal")
    ax.legend()
    plt.show()
    # Store the generated figures
    node.results["figures"] = {
        "amplitude": fig,
    }


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    pass


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
