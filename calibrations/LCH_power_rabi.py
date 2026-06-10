# %% {Imports}
import numpy as np
import xarray as xr

from qm.qua import *

from qualang_tools.loops import from_array
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_power_rabi import Parameters
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Description}
description = """
        POWER RABI (single pulse, customized)
A trimmed power-Rabi: sweep the qubit drive amplitude (as a pre-factor of the current
pulse amplitude) and fit a cosine to recalibrate the pi-pulse amplitude.

Differences vs 04b_power_rabi:
    - No error-amplification (N_pi) loop: the operation is played exactly once per
      amplitude point.
    - Uniform stream processing: always I_st[i].buffer(len(amps)).average() regardless
      of the operation.
    - drive_qubit selection: if drive_qubit is None, all qubits in qubits are driven;
      otherwise only that qubit is driven while all qubits are still read out.

Analysis is delegated to scqat's PowerRabiEstimator (cosine fit).

State update:
    - The qubit pulse amplitude of the selected operation
    (qubit.xy.operations[operation].amplitude); x90 is set to half when operation is x180
    and update_x90 is enabled.
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_power_rabi",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    node.parameters.qubits = ["q4", "q5"]
    node.parameters.multiplexed = True
    # node.parameters.operation = "x180"
    # node.parameters.min_amp_factor = 0.0
    # node.parameters.max_amp_factor = 1.99
    # node.parameters.amp_factor_step = 0.005
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

    n_avg = node.parameters.num_shots  # The number of averages
    operation = node.parameters.operation  # The qubit operation to play
    # Pulse amplitude sweep (as a pre-factor of the qubit pulse amplitude) - must be within [-2; 2)
    amps = np.arange(
        node.parameters.min_amp_factor,
        node.parameters.max_amp_factor,
        node.parameters.amp_factor_step,
    )
    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "amp_prefactor": xr.DataArray(amps, attrs={"long_name": "pulse amplitude prefactor"}),
    }

    with program() as node.namespace["qua_program"]:
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        if node.parameters.use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]
        a = declare(fixed)  # QUA variable for the qubit drive amplitude pre-factor

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)
                with for_(*from_array(a, amps)):
                    # Qubit initialization
                    for i, qubit in multiplexed_qubits.items():
                        qubit.reset(node.parameters.reset_type, node.parameters.simulate)
                    align()

                    # Qubit manipulation: play the operation once (no error amplification).
                    # Drive only the selected qubit, or all qubits when drive_qubit is None.
                    for i, qubit in multiplexed_qubits.items():
                        if node.parameters.drive_qubit is None or qubit.name == node.parameters.drive_qubit:
                            qubit.xy.play(operation, amplitude_scale=a)
                    align()

                    # Qubit readout
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
                # Uniform save: always buffer over amps and average, regardless of operation.
                if node.parameters.use_state_discrimination:
                    state_st[i].buffer(len(amps)).average().save(f"state{i + 1}")
                else:
                    I_st[i].buffer(len(amps)).average().save(f"I{i + 1}")
                    Q_st[i].buffer(len(amps)).average().save(f"Q{i + 1}")


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
    """Analyse the raw data with scqat: fit each qubit's power-Rabi cosine and store the
    fit results and figures. The estimator returns opt_amp_prefactor (the multiplier on
    the current pulse amplitude that yields a pi pulse) and a success flag."""
    from scqat.parsers import repetition_data
    from scqat.estimators.power_rabi import PowerRabiEstimator

    if node.parameters.use_state_discrimination:
        ds = node.results["ds_raw"].rename({"state": "signal"})
    else:
        ds = node.results["ds_raw"].rename({"I": "signal"})

    sep_data = repetition_data(ds, repetition_dim="qubit")
    node.results["fit_results"] = {}
    node.results["figures"] = {}
    estimator = PowerRabiEstimator()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        results, figs = estimator.analyze(sq_data, output_dir=None)
        node.results["fit_results"][qubit_name] = results
        node.results["figures"][qubit_name] = figs

    node.outcomes = {
        qubit_name: ("successful" if fit_result["success"] else "failed")
        for qubit_name, fit_result in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Figures are produced by the scqat estimator in analyse_data."""
    pass


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    operation = node.parameters.operation
    drive_qubit = node.parameters.drive_qubit
    with node.record_state_updates():
        for q in node.namespace["qubits"]:
            # When a single qubit is driven, only it is meaningfully calibrated; skip the
            # others so a cross-driven neighbour's oscillation can't rewrite its pi_amp.
            if drive_qubit is not None and q.name != drive_qubit:
                continue
            if node.outcomes[q.name] == "failed":
                continue

            prefactor = node.results["fit_results"][q.name]["opt_amp_prefactor"]
            opt_amp = prefactor * q.xy.operations[operation].amplitude
            q.xy.operations[operation].amplitude = opt_amp
            if operation == "x180" and node.parameters.update_x90:
                q.xy.operations["x90"].amplitude = opt_amp / 2


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
