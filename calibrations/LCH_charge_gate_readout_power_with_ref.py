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
from customized.node.LCH_charge_gate_readout_power_with_ref import (
    Parameters,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Description}
description = """
        Ask LCH
"""


node = QualibrationNode[Parameters, Quam](
    name="LCH_charge_gate_readout_power_with_ref",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    # You can get type hinting in your IDE by typing node.parameters.
    # node.parameters.qubits = ["q1", "q2"]
    node.parameters.simulate = True
    node.parameters.num_shots = 1
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

    p = node.parameters

    n_runs = p.num_shots  # Number of runs
    amps = np.linspace(p.start_amp, p.end_amp, p.num_amps)
    print(f"{qubits[0].charge_offset} charge offset")
    charge_gate_volts = np.arange(p.charge_gate_start_in_v, p.charge_gate_end_in_v +p.charge_gate_step_in_v/2, p.charge_gate_step_in_v)
    relative_charge_gate_volts = charge_gate_volts
    if (qubits[0].charge_offset + p.charge_gate_end_in_v) <= 0.5:
        charge_gate_volts = charge_gate_volts +qubits[0].charge_offset
        print(f"v+")
    else:
        charge_gate_volts = qubits[0].charge_offset -charge_gate_volts
        print(f"v-")

    ref_operation_name = p.ref_operation
    test_operation_name = p.test_operation

    # Register the sweep axes to be added to the dataset when fetching data
    prepared_states = p.prepared_states
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "prepared_state": xr.DataArray(prepared_states, attrs={"long_name": "prepared qubit state", "units": ""}),
        "charge_gate": xr.DataArray( relative_charge_gate_volts, attrs={"long_name": "charge gate volts", "units": "V"}),
        "amp_prefactor": xr.DataArray(amps, attrs={"long_name": "readout amplitude", "units": ""}),
        "shot_idx": xr.DataArray(np.linspace(1, n_runs, n_runs), attrs={"long_name": "number of shots"}),
    }
    with program() as node.namespace["qua_program"]:
        I_1, I_st_1, Q_1, Q_st_1, n, n_st = node.machine.declare_qua_variables()
        I_2, I_st_2, Q_2, Q_st_2, _, _ = node.machine.declare_qua_variables()
        I_3, I_st_3, Q_3, Q_st_3, _, _ = node.machine.declare_qua_variables()

        a = declare(fixed)
        ps = declare(int)
        charge_gate = declare(fixed)

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()
            with for_each_(ps, prepared_states):

                with for_(*from_array(charge_gate, charge_gate_volts)):
                    # ground iq blobs for all qubits
                    save(n, n_st)
                    
                    for qubit in multiplexed_qubits.values():
                        qubit.z.set_dc_offset(charge_gate)
                    align()
                    wait(1000000)
                    with for_(*from_array(a, amps)):

                        with for_(n, 0, n < n_runs, n + 1):


                            # Qubit initialization
                            for i, qubit in multiplexed_qubits.items():
                                qubit.reset(p.reset_type, p.simulate)
                            align()

                            # Qubit readout
                            for i, qubit in multiplexed_qubits.items():
                                qubit.resonator.measure(ref_operation_name, qua_vars=(I_1[i], Q_1[i]))
                                qubit.align()
                                # save data
                                save(I_1[i], I_st_1[i])
                                save(Q_1[i], Q_st_1[i])
                                wait( qubit.resonator.depletion_time//4, qubit.resonator.name )

                            # Change qubit state
                            for i, qubit in multiplexed_qubits.items():
                                qubit.align()

                                with switch_(ps):
                                    with case_(0):
                                        pass
                                    with case_(1):
                                        qubit.xy.play("x180")
                                    with case_(2):
                                        pass
                                        # qubit.xy.wait()

                                qubit.align()
                            # Qubit readout
                            for i, qubit in multiplexed_qubits.items():
                                qubit.resonator.measure(test_operation_name, qua_vars=(I_2[i], Q_2[i]), amplitude_scale=a)
                                qubit.align()
                                # save data
                                save(I_2[i], I_st_2[i])
                                save(Q_2[i], Q_st_2[i])

                                wait( qubit.resonator.depletion_time//4, qubit.resonator.name )

                            for i, qubit in multiplexed_qubits.items():
                                qubit.resonator.measure(ref_operation_name, qua_vars=(I_3[i], Q_3[i]))
                                qubit.align()
                                # save data
                                save(I_3[i], I_st_3[i])
                                save(Q_3[i], Q_st_3[i])

                                wait( qubit.resonator.depletion_time//4, qubit.resonator.name )


        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st_1[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"I{i + 1}_1")
                Q_st_1[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"Q{i + 1}_1")
                I_st_2[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"I{i + 1}_2")
                Q_st_2[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"Q{i + 1}_2")
                I_st_3[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"I{i + 1}_3")
                Q_st_3[i].buffer(n_runs).buffer(len(amps)).buffer(len(charge_gate_volts)).buffer(len(prepared_states)).save(f"Q{i + 1}_3")


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
            pass
            # progress_counter(
            #     data_fetcher.get("n", 0),
            #     node.parameters.num_shots,
            #     start_time=data_fetcher.t_start,
            # )
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
    pass
    # from qcat.parser.qm_reader import load_xarray_h5, repetition_data
    # from qcat.analysis.readout_power.analysis import ROFidelityPower

    # ds = node.results["ds_raw"]
    # sep_data = repetition_data(ds, repetition_dim="qubit")
    # node.results["figures"] = {}
    # for sq_data in sep_data:
    #     qubit_name = sq_data["qubit"].values.item()
    #     # Rename n_runs to shot_idx if present
    #     # sq_data = sq_data.rename({'n_runs': 'shot_idx','state': 'prepared_state'})
    #     print(sq_data)
    #     analysis = ROFidelityPower(sq_data)
    #     analysis._start_analysis()
       
    #     node.results["figures"][qubit_name] = analysis._plot_results(qubit_name)


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    pass

# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
