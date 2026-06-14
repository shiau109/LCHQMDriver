# %% {Imports}
import warnings

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
from customized.node.LCH_qubit_spectroscopy_flux import (
    Parameters,
    process_raw_dataset,
    fit_raw_data,
    log_fitted_results,
    plot_combined,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Description}
description = """
        QUBIT SPECTROSCOPY VERSUS FLUX — SINGLE FLUX / XY SOURCE (LCH / scqat analysis)
Maps the qubit response by sweeping a flux bias and the drive frequency, then extracts the qubit
frequency as a function of flux.

Built on the 03b frame, with two extra knobs:
  - `z_source_qubit`: when set, that single qubit's z-line drives the flux sweep while all qubits in
    `qubits` are read out. When None, each measured qubit fluxes itself (== 03b).
  - `xy_source_qubit`: when set, that single qubit's xy-line plays the saturation drive (its frequency
    is swept). When None, each measured qubit drives its own xy-line (== 03b).

Analysis is done by the scqat QubitSpectroscopyFluxEstimator, which fits the qubit peak flux-by-flux
(single Lorentzian per slice, with window enforcement + outlier rejection) to reduce the 2-D
(flux, detuning) map to a 1-D frequency(flux) trace. Turning that trace into state updates (the
flux-tunable transmon arch fit) is deferred — `update_state` is currently a no-op.

Prerequisites:
    - Having calibrated the readout (nodes 02a, 02b and/or 02c).
    - Having calibrated the qubit frequency (node 03a_qubit_spectroscopy.py).
    - Having specified the desired flux point (qubit.z.flux_point).
"""


node = QualibrationNode[Parameters, Quam](
    name="LCH_qubit_spectroscopy_flux",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    # You can get type hinting in your IDE by typing node.parameters.
    # node.parameters.qubits = ["q4", "q5"]
    # node.parameters.z_source_qubit = "q4"   # sweep only q1's flux
    # node.parameters.xy_source_qubit = "q5"  # drive only q1's xy
    # node.parameters.simulate = True
    # node.parameters.operation_amplitude_factor = 0.1
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
    num_qubits = len(qubits)
    # Check if the qubits have a z-line attached
    if any([q.z is None for q in qubits]):
        warnings.warn("Found qubits without a flux line. Skipping")

    operation = node.parameters.operation  # The qubit operation to play
    n_avg = node.parameters.num_shots
    # Adjust the pulse duration and amplitude to drive the qubit into a mixed state - can be None
    operation_len = node.parameters.operation_len_in_ns
    # pre-factor to the value defined in the config - restricted to [-2; 2)
    operation_amp = node.parameters.operation_amplitude_factor
    # Qubit drive detuning sweep with respect to the resonance frequency
    dfs = np.linspace(
        node.parameters.min_frequency_in_mhz * u.MHz,
        node.parameters.max_frequency_in_mhz * u.MHz,
        node.parameters.num_frequency_points,
    )
    # Flux bias sweep in V
    dcs = np.linspace(
        node.parameters.min_flux_amp_in_v,
        node.parameters.max_flux_amp_in_v,
        node.parameters.num_flux_points,
    )

    # Resolve the single flux / xy source qubits (if any). When None, each measured
    # qubit drives its own z- / xy-line (identical to the official 03b node).
    z_source_qubit = (
        None if node.parameters.z_source_qubit is None
        else node.machine.qubits[node.parameters.z_source_qubit]
    )
    xy_source_qubit = (
        None if node.parameters.xy_source_qubit is None
        else node.machine.qubits[node.parameters.xy_source_qubit]
    )

    # Saturation duration (Python-level): uniform when operation_len is given, else
    # taken from the driving qubit's operation length.
    ref_qubit = xy_source_qubit if xy_source_qubit is not None else next(iter(qubits))
    operation_duration = (
        operation_len * u.ns if operation_len is not None
        else ref_qubit.xy.operations[operation].length * u.ns
    )

    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "qubit frequency", "units": "Hz"}),
        "flux_bias": xr.DataArray(dcs, attrs={"long_name": "flux bias", "units": "V"}),
    }

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        df = declare(int)  # QUA variable for the qubit drive frequency detuning
        dc = declare(fixed)  # QUA variable for the flux dc level

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)
                with for_(*from_array(df, dfs)):
                    with for_(*from_array(dc, dcs)):
                        # Qubit initialization: thermalize to the ground state.
                        for i, qubit in multiplexed_qubits.items():
                            qubit.reset_qubit_thermal()
                        # Update the drive frequency on whichever xy-line plays.
                        if xy_source_qubit is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                        else:
                            xy_source_qubit.xy.update_frequency(df + xy_source_qubit.xy.intermediate_frequency)
                        align()

                        # Bring the qubit(s) to the flux point during the saturation pulse.
                        if z_source_qubit is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.z.play(
                                    "const",
                                    amplitude_scale=dc / qubit.z.operations["const"].amplitude,
                                    duration=operation_duration,
                                )
                        else:
                            z_source_qubit.z.play(
                                "const",
                                amplitude_scale=dc / z_source_qubit.z.operations["const"].amplitude,
                                duration=operation_duration,
                            )
                        # Apply the saturation drive: from each qubit, or a single xy source.
                        if xy_source_qubit is None:
                            for i, qubit in multiplexed_qubits.items():
                                qubit.xy.play(operation, amplitude_scale=operation_amp, duration=operation_duration)
                        else:
                            xy_source_qubit.xy.play(operation, amplitude_scale=operation_amp, duration=operation_duration)
                        align()

                        # Readout every measured qubit's resonator.
                        for i, qubit in multiplexed_qubits.items():
                            qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                            save(I[i], I_st[i])
                            save(Q[i], Q_st[i])

            # Measure sequentially
            if not node.parameters.multiplexed:
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st[i].buffer(len(dcs)).buffer(len(dfs)).average().save(f"I{i + 1}")
                Q_st[i].buffer(len(dcs)).buffer(len(dfs)).average().save(f"Q{i + 1}")


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
    """Fit the qubit peak flux-by-flux with scqat to reduce the 2-D map to a 1-D
    frequency(flux) trace. The per-qubit (slice, results) pairs are kept in the
    namespace so plot_data can redraw the figures without refitting."""
    ds = process_raw_dataset(node.results["ds_raw"], node)
    node.results["ds_raw"] = ds
    sep_results, fit_results = fit_raw_data(ds, node)
    node.namespace["sep_results"] = sep_results
    node.results["fit_results"] = fit_results

    # Log the per-slice (flux-by-flux) peak-fit summary
    log_fitted_results(node.results["fit_results"], log_callable=node.log)
    node.outcomes = {
        qubit_name: ("successful" if fit_result["success"] else "failed")
        for qubit_name, fit_result in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate or not node.parameters.plot)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """One combined figure per qubit: the 2-D signal map with the per-flux fitted
    qubit-frequency centres overlaid."""
    node.results["figures"] = plot_combined(node.namespace["sep_results"])
    plt.show()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Deferred: turning the frequency(flux) trace into state updates (idle offset,
    sweet-spot f_01, ...) needs the flux-tunable transmon arch fit, which is still
    to be designed. No state is updated for now."""
    pass


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
