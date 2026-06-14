# %% {Imports}
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr

from qm.qua import *

from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_readout_fidelity import (
    Parameters,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Description}
description = """
        Ask LCH
"""
# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_readout_fidelity",  # Name should be unique
    description=description,  # Describe what the node is doing, which is also reflected in the QUAlibrate GUI
    parameters=Parameters(),  # Node parameters defined under quam_experiment/experiments/node_name
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """
    Allow the user to locally set the node parameters for debugging purposes, or
    execution in the Python IDE.
    """
    # You can get type hinting in your IDE by typing node.parameters.
    node.parameters.qubits = ["q4", "q5"]
    node.parameters.multiplexed = True
    node.parameters.num_shots = 4000
    pass


# Instantiate the QUAM class from the state file
node.machine = Quam.load()


# %% {Create_QUA_program}
@node.run_action(skip_if=node.parameters.load_data_id is not None)
def create_qua_program(node: QualibrationNode[Parameters, Quam]):
    """
    Create the sweep axes and generate the QUA program from the pulse sequence and the
    node parameters.
    """
    # Class containing tools to help handle units and conversions.
    u = unit(coerce_to_integer=True)
    # Get the active qubits from the node and organize them by batches
    node.namespace["qubits"] = qubits = get_qubits(node)
    num_qubits = len(qubits)
    operation = node.parameters.operation
    n_runs = node.parameters.num_shots  # Number of runs
    prepared_states = [0, 1]

    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "shot_idx": xr.DataArray(np.arange(1, n_runs + 1), attrs={"long_name": "number of shots"}),
        "prepared_state": xr.DataArray(prepared_states, attrs={"long_name": "prepared qubit state", "units": ""}),
    }

    with program() as node.namespace["qua_program"]:
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        ps = declare(int)

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_runs, n + 1):
                # ground iq blobs for all qubits
                save(n, n_st)
                with for_each_(ps, prepared_states):
                    # Qubit initialization
                    for i, qubit in multiplexed_qubits.items():
                        qubit.reset(node.parameters.reset_type, node.parameters.simulate)
                    align()

                    # Change qubit state
                    for i, qubit in multiplexed_qubits.items():
                        qubit.align()

                        with switch_(ps):
                            with case_(0):
                                pass
                            with case_(1):
                                qubit.xy.play("x180")

                        qubit.align()
                    # Qubit readout
                    for i, qubit in multiplexed_qubits.items():
                        qubit.resonator.measure(operation, qua_vars=(I[i], Q[i]))
                        qubit.align()
                        # save data
                        save(I[i], I_st[i])
                        save(Q[i], Q_st[i])

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st[i].buffer(len(prepared_states)).buffer(n_runs).save(f"I{i + 1}")
                Q_st[i].buffer(len(prepared_states)).buffer(n_runs).save(f"Q{i + 1}")


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
    """
    Connect to the QOP, execute the QUA program and fetch the raw data and store it in a xarray dataset called "ds_raw".
    """
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
    """Characterise single-shot readout fidelity at the current settings. For each
    qubit scqat's StateDiscriminationEstimator fits the IQ blobs; the readout fidelity
    is the mean of the confusion-matrix diagonal (direct_counts[k, k]). Figures are
    deferred to plot_data, so the fit is skipped only once.

    ds_raw already carries the I/Q vars and shot_idx/prepared_state coords that scqat
    expects (see sweep_axes above), so no renaming is needed."""
    from scqat.parsers import repetition_data
    from scqat.estimators.state_discrimination import StateDiscriminationEstimator

    estimator = StateDiscriminationEstimator()
    node.namespace["estimator"] = estimator
    node.namespace["sep_results"] = {}
    node.results["fit_results"] = {}

    for sq in repetition_data(node.results["ds_raw"], repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        results = estimator.analyze(sq, output_dir=None, skip_figures=True)[0]
        dc = np.asarray(results["direct_counts"])
        n = min(dc.shape[0], dc.shape[1])
        fidelity = float(np.mean([dc[k, k] for k in range(n)]))
        # SNR = |mean_1 - mean_0| / sigma: the IQ-plane separation of the two readout
        # blobs in units of one blob's (GMM) standard deviation.
        tp = results["trained_paras"]
        centers = np.asarray(tp["mean"], dtype=float)
        sigma = float(tp["std"])
        snr = (
            float(np.linalg.norm(centers[0] - centers[1]) / sigma)
            if centers.shape[0] >= 2 and sigma > 0 else float("nan")
        )
        node.results["fit_results"][qubit_name] = {
            "fidelity": fidelity,
            "snr": snr,
            "success": bool(np.isfinite(fidelity) and fidelity >= 0.5),
        }
        node.namespace["sep_results"][qubit_name] = (sq, results)

    for q_name, fit in node.results["fit_results"].items():
        node.log(
            f"Results for qubit {q_name}: "
            f"readout fidelity: {fit['fidelity']:.4f} | "
            f"SNR: {fit['snr']:.2f} | "
            f"{'SUCCESS!' if fit['success'] else 'FAIL!'}"
        )
    node.outcomes = {
        qubit_name: ("successful" if fit["success"] else "failed")
        for qubit_name, fit in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate or not node.parameters.plot)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Redraw the scqat state-discrimination figures for each qubit from the stored
    (dataset, results) pairs."""
    estimator = node.namespace["estimator"]
    node.results["figures"] = {}
    for qubit_name, (sq, results) in node.namespace["sep_results"].items():
        node.results["figures"][qubit_name] = estimator.generate_figures(sq, results)
    plt.show()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """No state write-back: this node only characterises single-shot readout fidelity
    at the current settings, so there is no single scalar to commit. Deriving the
    readout angle / threshold / confusion matrix from the GMM is a separate
    calibration (cf. the readout-frequency and readout-power nodes, which do write
    their optimum back)."""
    pass

# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
