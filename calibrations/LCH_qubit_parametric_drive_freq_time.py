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
from customized.node.LCH_qubit_parametric_drive_time import Parameters
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Node initialisation}
description = """
        Parametric-drive qubit decoherence (rho_11 vs frequency and time).

        Prepares the qubit, applies a fixed-amplitude parametric (flux-line) drive
        while sweeping the drive frequency and duration, then reads out. With
        `tomography=False` (default) it prepares |1> and reads out the excited-state
        population directly (rho_11-only). With `tomography=True` it sweeps an extra
        X/Y/Z readout-basis axis for full single-qubit state tomography (set
        `prepare_state` to a superposition, e.g. "x90"/"-x90"). Either way scqat's
        ParametricDriveDecoherenceEstimator reconstructs rho_11(t), fits the
        non-Markovian amplitude-damping model per driving frequency, and reports
        gamma / lambda / Delta and the exceptional-point figure of merit
        8*lambda^2/gamma^2 vs frequency. Characterization only — no device-state
        writeback.
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_qubit_parametric_drive_freq_time",  # Name should be unique
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
    node.parameters.max_driving_time_ns = 420
    node.parameters.min_driving_time_ns = 20
    node.parameters.driving_time_step = 8
    node.parameters.max_frequency_mhz = 376
    node.parameters.min_frequency_mhz = 374
    node.parameters.frequency_points = 6
    node.parameters.driving_amp_ratio = 1.4
    node.parameters.use_state_discrimination = True
    node.parameters.simulate = False
    node.parameters.num_shots = 400
    node.parameters.multiplexed = True
    # Set tomography = True (and a superposition prepare_state) for full X/Y/Z tomography.
    # node.parameters.tomography = True
    # node.parameters.prepare_state = "-x90"
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

    # X/Y/Z readout-basis axis — only swept when tomography is enabled.
    readout_basis_array = [0, 1, 2]

    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "driving_frequency": xr.DataArray(freqs, attrs={"long_name": "driving frequency", "units": "Hz"}),
        "driving_time": xr.DataArray(time_ns, attrs={"long_name": "driving time", "units": "ns"}),
    }
    if p.tomography:
        node.namespace["sweep_axes"]["basis"] = xr.DataArray(
            readout_basis_array, attrs={"long_name": "basis for state tomography"}
        )

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        tt = declare(int)  # QUA variable for the driving time
        f_drive = declare(int)  # QUA variable for the driving frequency
        rbi = declare(int)  # readout-basis index (used only when tomography is on)

        if node.parameters.use_state_discrimination:
            state = [declare(int) for _ in range(num_qubits)]
            state_st = [declare_stream() for _ in range(num_qubits)]

        def measure_shot(multiplexed_qubits, rbi_var):
            """One prepare -> parametric-drive -> (optional basis rotation) -> readout
            shot. When ``rbi_var`` is given, the readout basis is selected by it
            (X: -y90, Y: x90, Z: identity) for state tomography."""
            for i, qubit in multiplexed_qubits.items():
                qubit.reset(
                    node.parameters.reset_type,
                    node.parameters.simulate,
                    log_callable=node.log,
                )
                # Update the qubit frequency
                qubit.z.update_frequency(f_drive)

            for i, qubit in multiplexed_qubits.items():
                qubit.xy.play(node.parameters.prepare_state)
            align()
            wait(200 // 4)
            for i, qubit in multiplexed_qubits.items():
                if i == 0:
                    qubit.z.reset_if_phase()
                    qubit.z.play("parametric_reset", amplitude_scale=p.driving_amp_ratio, duration=tt)
            align()

            if rbi_var is not None:
                # Rotate into the measured basis before readout.
                for i, qubit in multiplexed_qubits.items():
                    with switch_(rbi_var):
                        with case_(0):
                            qubit.xy.play("-y90")
                        with case_(1):
                            qubit.xy.play("x90")
                        with case_(2):
                            qubit.xy.play("y90", amplitude_scale=0)
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

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)
                with for_(*from_array(f_drive, freqs)):
                    with for_(*from_array(tt, time_tick)):
                        if p.tomography:
                            with for_each_(rbi, readout_basis_array):
                                measure_shot(multiplexed_qubits, rbi)
                        else:
                            measure_shot(multiplexed_qubits, None)

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                if node.parameters.use_state_discrimination:
                    stream = state_st[i].buffer(len(readout_basis_array)) if p.tomography else state_st[i]
                    stream.buffer(len(time_tick)).buffer(len(freqs)).average().save(f"state{i + 1}")
                else:
                    i_stream = I_st[i].buffer(len(readout_basis_array)) if p.tomography else I_st[i]
                    q_stream = Q_st[i].buffer(len(readout_basis_array)) if p.tomography else Q_st[i]
                    i_stream.buffer(len(time_tick)).buffer(len(freqs)).average().save(f"I{i + 1}")
                    q_stream.buffer(len(time_tick)).buffer(len(freqs)).average().save(f"Q{i + 1}")


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
    """estimate: per-driving_frequency non-Markovian decoherence fit via scqat's
    ParametricDriveDecoherenceEstimator.

    The estimator auto-detects the layout: with tomography it rebuilds the density
    matrix from the X/Y/Z basis readouts; without it, it takes the rho_11-only path.
    Either way it fits rho_11(t) at each driving frequency and returns gamma / lambda /
    Delta and the exceptional-point figure of merit 8*lambda^2/gamma^2. The estimator
    owns the plotting, so no separate plot step is needed."""
    from scqat.parsers import repetition_data
    from scqat.estimators import ParametricDriveDecoherenceEstimator

    ds = node.results["ds_raw"]
    analyze_kwargs = {}
    if not node.parameters.use_state_discrimination:
        ds = ds.rename({"I": "signal"})
        # Raw I quadrature is NOT a population — supply this qubit's readout-contrast
        # correction so rho_11 lands in [0,1]. (The estimator default is identity,
        # which is correct for the state-discriminated path below.)
        analyze_kwargs = dict(rho11_offset=0.045, rho11_scale=0.78)

    sep_data = repetition_data(ds, repetition_dim="qubit")
    node.results["fit_results"] = {}
    node.results["figures"] = {}
    estimator = ParametricDriveDecoherenceEstimator()
    for sq_data in sep_data:
        qubit_name = sq_data["qubit"].values.item()
        # With state discrimination, `state` is already P(|1>) in [0,1], so the
        # estimator's identity default (rho11_offset=0, rho11_scale=1) is used as-is.
        results, figs = estimator.analyze(
            sq_data, output_dir=None, skip_figures=not node.parameters.plot, **analyze_kwargs
        )
        node.results["fit_results"][qubit_name] = estimator.extract_metadata(results)
        node.results["figures"][qubit_name] = figs


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """No-op: this is a characterization experiment, so nothing is written back
    to the device state."""
    pass


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
