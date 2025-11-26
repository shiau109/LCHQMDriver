# %% {Imports}
import warnings
from dataclasses import asdict

import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
from qm.qua import *
from qualang_tools.loops import from_array
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit
from qualibrate import QualibrationNode
from quam_config import Quam
from calibration_utils.LCH_CZ_conditional_phase import (
    Parameters,
    fit_raw_data,
    log_fitted_results,
    plot_raw_data_with_fit,
    process_raw_dataset,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher

# %% {Description}
description = """
        Ask LCH 
"""


node = QualibrationNode[Parameters, Quam](
    name="LCH_CZ_phase_compensation",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    # You can get type hinting in your IDE by typing node.parameters.
    # node.parameters.qubits = ["q1", "q3"]

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
    num_qubits = len(qubits)
    # Check if the qubits have a z-line attached
    if any([q.z is None for q in qubits]):
        warnings.warn("Found qubits without a flux line. Skipping")


    qubit_sweep = node.machine.qubits[node.parameters.qubit_sweep]
    qubit_fixed = node.machine.qubits[node.parameters.qubit_fixed]
    qubit_pair = node.machine.qubit_pairs[node.parameters.qubit_pair]
    coupler = qubit_pair.coupler

    operation = node.parameters.operation  # The qubit operation to play
    operation_times = node.parameters.operation_times  # The operation length in ns
    n_avg = node.parameters.num_shots
    operation_gap_ns = node.parameters.operation_gap_ns

    flux_idle_case = node.parameters.flux_idle_case

    ctrl_switch = [True, False]  # Control of CZ
    readout_angle_array = np.linspace(-0.75, 0.75, node.parameters.readout_angle_point)  # Readout basis index (0 or 1)

    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "ctrl_switch": xr.DataArray(np.array(ctrl_switch), attrs={"long_name": "control switch", "units": "arb."}),
        "basis": xr.DataArray(np.array(readout_angle_array), attrs={"long_name": "reaout basis angle", "units": "2pi"}),
    }

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        c_sw = declare(bool)  # QUA variable for the CZ control switch
        roa = declare(fixed)  # QUA variable for readout basis index

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
                with for_each_(c_sw, ctrl_switch):
                    with for_(*from_array(roa,readout_angle_array) ):

                        # Qubit initialization
                        for i, qubit in multiplexed_qubits.items():
                            # Wait for the qubits to decay to the ground state
                            qubit.reset(
                                node.parameters.reset_type,
                                node.parameters.simulate,
                                log_callable=node.log,
                            )
                            qubit.xy.reset_if_phase()
                            # Flux sweeping for a qubit
                        align()

                        # Qubit manipulation
                        with if_(c_sw):
                            qubit_sweep.xy.play("y90")

                            align()
                            wait(16//4)

                            for _ in range(operation_times):
                                qubit_sweep.z.play(operation)
                                coupler.play(operation)
                                wait(operation_gap_ns//4)
                                qubit_sweep.xy.frame_rotation_2pi(0.1)
                                qubit_sweep.xy.play("x180",amplitude_scale=0)
                                qubit_sweep.xy.frame_rotation_2pi(roa)
                            align()
                            
                            
                            qubit_sweep.xy.play("-y90")

                        with else_():
                            qubit_fixed.xy.play("y90")
                            align()
                            wait(16//4)

                            for _ in range(operation_times):
                                qubit_sweep.z.play(operation)
                                coupler.play(operation)
                                wait(operation_gap_ns//4)
                                qubit_fixed.xy.frame_rotation_2pi(0.38)
                                qubit_fixed.xy.play("x180",amplitude_scale=0)
                                qubit_fixed.xy.frame_rotation_2pi(roa)
                            align()

                            
                            qubit_fixed.xy.play("-y90")


                        wait(16//4)

                        # Measure the state of the resonators
                        for i, qubit in multiplexed_qubits.items():
                            if node.parameters.use_state_discrimination:
                                qubit.readout_state(state[i])
                                save(state[i], state_st[i])
                            else:
                                qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                                # save data
                                save(I[i], I_st[i])
                                save(Q[i], Q_st[i])


            # Measure sequentially
            if not node.parameters.multiplexed:
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                if node.parameters.use_state_discrimination:
                    state_st[i].buffer(len(readout_angle_array)).buffer(len(ctrl_switch)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(readout_angle_array)).buffer(len(ctrl_switch)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(readout_angle_array)).buffer(len(ctrl_switch)).average().save(f"Q{i + 1}")



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
    # node.namespace["qubits"] = get_qubits(node)
    # ds_processed = process_raw_dataset(node.results["ds_raw"], node)
    # ds_processed.IQ_abs.plot()


# %% {Analyse_data}
@node.run_action(skip_if=node.parameters.simulate)
def analyse_data(node: QualibrationNode[Parameters, Quam]):
    """Analyse the raw data and store the fitted data in another xarray dataset "ds_fit" and the fitted results in the "fit_results" dictionary."""
    node.results["ds_raw"] = process_raw_dataset(node.results["ds_raw"], node)
    # node.results["ds_fit"], fit_results = fit_raw_data(node.results["ds_raw"], node)
    # node.results["fit_results"] = {k: asdict(v) for k, v in fit_results.items()}

    # # Log the relevant information extracted from the data analysis
    # log_fitted_results(node.results["fit_results"], log_callable=node.log)
    # node.outcomes = {
    #     qubit_name: ("successful" if fit_result["success"] else "failed")
    #     for qubit_name, fit_result in node.results["fit_results"].items()
    # }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Plot the raw and fitted data in specific figures whose shape is given by qubit.grid_location."""
    # if node.parameters.use_state_discrimination:
    #     da = node.results["ds_raw"]["state"]
    # else:
    #     da = node.results["ds_raw"]["I"]
    fig_raw_fit = plot_raw_data_with_fit(node.results["ds_raw"], node.namespace["qubits"])
    plt.show()
    # Store the generated figures
    node.results["figures"] = {
        "amplitude": fig_raw_fit,
    }


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    # with node.record_state_updates():
    #     for q in node.namespace["qubits"]:
    #         if node.outcomes[q.name] == "failed":
    #             continue
    #         else:
    #             fit_results = node.results["fit_results"][q.name]
    #             if node.parameters.flux_idle_case == "independent":
    #                 q.z.independent_offset += fit_results["idle_offset"]
    #             elif node.parameters.flux_idle_case == "joint":
    #                 q.z.joint_offset += fit_results["idle_offset"]
    #             q.xy.RF_frequency = fit_results["qubit_frequency"]
    #             q.f_01 = fit_results["qubit_frequency"]
                # q.freq_vs_flux_01_quad_term = fit_results["quad_term"]


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
