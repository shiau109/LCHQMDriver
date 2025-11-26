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
from calibration_utils.LCH_time_dep_rr_photon import (
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
    name="LCH_time_dep_rr_photon",
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

    ro_operation = node.parameters.ro_operation  # The resonator operation to play

    n_avg = node.parameters.num_shots

    xy_operation = node.parameters.xy_operation  # The qubit operation to play
    xy_operation_len = node.parameters.xy_operation_len_in_ns
    xy_operation_amp = node.parameters.xy_operation_amplitude_factor


    xy_time_resolution_in_ns = node.parameters.xy_time_resolution_in_ns * u.ns # ns
    xy_max_delay_in_ns = node.parameters.xy_max_delay_in_ns  # ns

    delay_tick_array = np.arange(0, xy_max_delay_in_ns + 1, xy_time_resolution_in_ns) // 4
    delay_time_array = delay_tick_array * 4  # in ns

    rr_depletion_time = node.parameters.rr_depletion_time

    # Qubit detuning sweep with respect to their resonance frequencies
    point_freq = node.parameters.num_frequency_points
    dfs = np.linspace(node.parameters.min_frequency_in_mhz* u.MHz, node.parameters.max_frequency_in_mhz* u.MHz, point_freq)
    # Flux bias sweep in V
    flux_idle_case = node.parameters.flux_idle_case


    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "qubit frequency", "units": "Hz"}),
        "delay_time": xr.DataArray(delay_time_array, attrs={"long_name": "delay time", "units": "ns"}),
    }

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        df = declare(int)  # QUA variable for the qubit frequency
        delay_tick = declare(int)  # QUA variable for the flux dc level
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
                with for_(*from_array(df, dfs)):
                    with for_(*from_array(delay_tick, delay_tick_array)):
                        # Qubit initialization
                        for i, qubit in multiplexed_qubits.items():
                            # Update the qubit frequency
                            qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                            # Wait for the qubits to decay to the ground state
                            qubit.reset(node.parameters.reset_type, node.parameters.simulate)
                            # Flux sweeping for a qubit

                            xy_duration = (
                                xy_operation_len * u.ns
                                if xy_operation_len is not None
                                else qubit.xy.operations[xy_operation].length * u.ns
                            )
                            
                        align()

                        # Qubit manipulation
                        # Bring the qubit to the desired point during the saturation pulse

                        for i, qubit in multiplexed_qubits.items():
                            # Apply saturation pulse to all qubits

                            wait( (xy_duration*5+16)//4, qubit.resonator.name)
                            qubit.resonator.play(ro_operation)
                            wait( delay_tick+4, qubit.xy.name)
                            qubit.xy.play(  xy_operation, duration=xy_duration//4, amplitude_scale=xy_operation_amp )
                            
                            if rr_depletion_time is not None:
                                wait( rr_depletion_time * u.ns//4, qubit.resonator.name )
                            else:
                                wait( qubit.resonator.depletion_time * u.ns//4, qubit.resonator.name )
                        align()
                        
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
                    state_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(delay_time_array)).buffer(len(dfs)).average().save(f"Q{i + 1}")



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
    pass


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Plot the raw and fitted data in specific figures whose shape is given by qubit.grid_location."""
    node.results["figures"] = {}
    from qcat.parser.qm_reader import repetition_data
    from qcat.utilities.simple_visualization import plot_2d_colormap_from_h5
    ds = node.results["ds_raw"]

    for sq_data in repetition_data(ds):
        qubit_name = sq_data["qubit"].values.item()


        from qcat.analysis.readout_pulse_photon.analysis import Readout_pulse_shaping
        from qcat.analysis.readout_pulse_photon.visualization import plot_all

        plot_info=dict(P_rescale=False, #normalize contrast to population
               Dis=None,
               linecut=0, 
               readout_qubit_info=True,
               color_bound=False,
               bound_value=[0,1],
               log_scale=False)

        fit_info=dict(Photon_convert=False,
                    Ac_info=None,
                    X_eff=None)
        
        from types import SimpleNamespace
        Raw_data = SimpleNamespace(
            meas_q = qubit_name,
            first_samples=ds.coords["detuning"].values,
            second_samples=ds.coords["delay_time"].values
        )
        Process_data_rpsh = { "data": [sq_data["I"].transpose('delay_time','detuning').values],
                    "first_samples":sq_data.coords["detuning"].values,
                    "second_samples":sq_data.coords["delay_time"].values
        }

        result_rpsh = Readout_pulse_shaping(Raw_data,Process_data_rpsh)
        node.results["figures"][qubit_name] = plot_all(Raw_data,Process_data_rpsh,result_rpsh,fit_info,plot_info, Save=False, Save_graph_path=None, id=None)        



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
