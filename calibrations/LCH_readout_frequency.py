# %% {Imports}
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
from customized.node.LCH_readout_frequency import (
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
    name="LCH_readout_frequency",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    # You can get type hinting in your IDE by typing node.parameters.
    # node.parameters.qubits = ["q1", "q2"]
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

    n_runs = node.parameters.num_shots  # Number of runs

    step = node.parameters.frequency_step_in_mhz * u.MHz
    dfs = np.arange(node.parameters.start_freq_in_mhz * u.MHz, node.parameters.end_freq_in_mhz * u.MHz, step)

    # Register the sweep axes to be added to the dataset when fetching data
    prepared_states = [0, 1]
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "shot_idx": xr.DataArray(np.arange(1, n_runs + 1), attrs={"long_name": "number of shots"}),
        "frequency": xr.DataArray(dfs, attrs={"long_name": "readout frequency", "units": "Hz"}),
        "prepared_state": xr.DataArray(prepared_states, attrs={"long_name": "prepared qubit state", "units": ""}),
    }
    with program() as node.namespace["qua_program"]:
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        df = declare(int)
        ps = declare(int)
        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_runs, n + 1):
                # ground iq blobs for all qubits
                save(n, n_st)
                with for_(*from_array(df, dfs)):
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
                            update_frequency(qubit.resonator.name, df + qubit.resonator.intermediate_frequency)
                            qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                            qubit.align()
                            # save data
                            save(I[i], I_st[i])
                            save(Q[i], Q_st[i])



        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st[i].buffer(len(prepared_states)).buffer(len(dfs)).buffer(n_runs).save(f"I{i + 1}")
                Q_st[i].buffer(len(prepared_states)).buffer(len(dfs)).buffer(n_runs).save(f"Q{i + 1}")


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
    """Find the readout frequency that maximises single-shot fidelity. For each qubit
    the swept-frequency state-discrimination data is handed to scqat's
    ReadoutFreqFidelityEstimator, which returns the optimal detuning (relative to the
    current readout IF the sweep was centred on) and the fidelity there. Figures are
    deferred to plot_data, so the fit is skipped only once.

    ds_raw already carries the I/Q vars and shot_idx/frequency/prepared_state coords
    that scqat expects (see sweep_axes above), so no renaming is needed."""
    from scqat.parsers import repetition_data
    from scqat.estimators.readout_fidelity import ReadoutFreqFidelityEstimator

    estimator = ReadoutFreqFidelityEstimator()
    node.namespace["estimator"] = estimator
    node.namespace["sep_results"] = {}
    node.results["fit_results"] = {}

    for sq in repetition_data(node.results["ds_raw"], repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        results = estimator.analyze(sq, output_dir=None, skip_figures=True)[0]
        best = results["best_sweep_value"]
        node.results["fit_results"][qubit_name] = {
            "best_detuning": float(best) if best is not None else float("nan"),
            "best_fidelity": float(results["best_fidelity"]) if results["best_fidelity"] is not None else float("nan"),
            "success": bool(results["success"]),
        }
        node.namespace["sep_results"][qubit_name] = (sq, results)

    for q_name, fit in node.results["fit_results"].items():
        node.log(
            f"Results for qubit {q_name}: "
            f"optimal detuning: {1e-6 * fit['best_detuning']:.3f} MHz | "
            f"fidelity: {fit['best_fidelity']:.4f} | "
            f"{'SUCCESS!' if fit['success'] else 'FAIL!'}"
        )
    node.outcomes = {
        qubit_name: ("successful" if fit["success"] else "failed")
        for qubit_name, fit in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate or not node.parameters.plot)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Redraw the scqat readout-frequency fidelity figures for each qubit from the
    stored (dataset, results) pairs."""
    estimator = node.namespace["estimator"]
    node.results["figures"] = {}
    for qubit_name, (sq, results) in node.namespace["sep_results"].items():
        node.results["figures"][qubit_name] = estimator.generate_figures(sq, results)
    plt.show()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Shift each qubit's readout frequency by the optimal detuning found above
    (the sweep spans a detuning around the current readout IF)."""
    with node.record_state_updates():
        for q in node.namespace["qubits"]:
            if node.outcomes[q.name] == "failed":
                continue

            best_detuning = node.results["fit_results"][q.name]["best_detuning"]
            q.resonator.RF_frequency = float(q.resonator.RF_frequency + best_detuning)

# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
