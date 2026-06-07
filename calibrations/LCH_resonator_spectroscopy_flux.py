# %% {Imports}
import matplotlib.pyplot as plt
import numpy as np
import xarray as xr
import warnings

from qm.qua import *

from qualang_tools.loops import from_array
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualang_tools.units import unit

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_resonator_spectroscopy_flux import (
    Parameters,
    process_raw_dataset,
    fit_raw_data,
    log_fitted_results,
    fit_flux_dependence,
    log_dispersion_results,
    plot_combined,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Node initialisation}
description = """
        RESONATOR SPECTROSCOPY VERSUS FLUX — SINGLE FLUX SOURCE (LCH / scqat analysis)
Maps the resonator response by sweeping a flux bias and the readout frequency, then extracts the
resonator centre frequency as a function of flux.

Unlike the official 02c node — which forces every measured qubit to drive its own z-line — this node
adds a `z_source_qubit` parameter: when set, that single qubit's z-line drives the flux sweep while all
qubits in `qubits` are read out (e.g. to see how one flux line shifts other resonators). When
`z_source_qubit` is None the behaviour is identical to 02c (each qubit fluxes itself).

Analysis is done by the scqat ResonatorSpectroscopyVsFluxEstimator, which fits the resonator dip
flux-by-flux (single inverted Lorentzian per slice) to reduce the 2-D (flux, detuning) map to a 1-D
centre-frequency(flux) trace. Turning that trace into state updates (sweet spot, idle offset, phi0) is
deferred — `update_state` is currently a no-op.

Prerequisites:
    - Having calibrated the resonator frequency (nodes 02a, 02b and/or 02c).
    - Having specified the desired flux point (qubit.z.flux_point).
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_resonator_spectroscopy_flux",  # Name should be unique
    description=description,  # Describe what the node is doing, which is also reflected in the QUAlibrate GUI
    parameters=Parameters(),  # Node parameters defined under quam_experiment/experiments/node_name
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    # You can get type hinting in your IDE by typing node.parameters.
    node.parameters.qubits = ["q4", "q5"]
    node.parameters.z_source_qubit = "q5"  # sweep only q1's flux while reading the listed resonators
    # node.parameters.simulate = True
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
    # Extract the sweep parameters and axes from the node parameters
    n_avg = node.parameters.num_shots
    # Flux bias sweep in V
    dcs = np.linspace(
        node.parameters.min_flux_offset_in_v,
        node.parameters.max_flux_offset_in_v,
        node.parameters.num_flux_points,
    )
    # The frequency sweep around the resonator resonance frequency
    span = node.parameters.frequency_span_in_mhz * u.MHz
    step = node.parameters.frequency_step_in_mhz * u.MHz
    dfs = np.arange(-span / 2, +span / 2, step)

    # Resolve the single flux-source qubit (if any). When None, each measured
    # qubit drives its own z-line (identical to the official 02c node).
    if node.parameters.z_source_qubit is None:
        z_source_qubit = None
    else:
        z_source_qubit = node.machine.qubits[node.parameters.z_source_qubit]

    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "flux_bias": xr.DataArray(dcs, attrs={"long_name": "flux bias", "units": "V"}),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "readout frequency", "units": "Hz"}),
    }

    # The QUA program stored in the node namespace to be transfer to the simulation and execution run_actions
    with program() as node.namespace["qua_program"]:
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        dc = declare(fixed)  # QUA variable for the flux bias
        df = declare(int)  # QUA variable for the readout frequency detuning
        idx = declare(int)  # progress index over the outer flux loop

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            assign(idx, 0)
            with for_(*from_array(dc, dcs)):
                # Save the flux-point counter for the progress bar
                save(idx, n_st)
                assign(idx, idx + 1)
                # Apply the flux: either from the single source qubit, or per-qubit (== 02c).
                if z_source_qubit is None:
                    for i, qubit in multiplexed_qubits.items():
                        qubit.z.set_dc_offset(dc)
                        qubit.z.settle()
                else:
                    z_source_qubit.z.set_dc_offset(dc)
                    z_source_qubit.z.settle()
                align()

                # Read out every measured qubit's resonator at this flux bias.
                for i, qubit in multiplexed_qubits.items():
                    rr = qubit.resonator
                    with for_(*from_array(df, dfs)):
                        # Update the resonator frequencies for resonator
                        rr.update_frequency(df + rr.intermediate_frequency)
                        # Average innermost: repeat the measurement n_avg times per point
                        with for_(n, 0, n < n_avg, n + 1):
                            # readout the resonator
                            rr.measure("readout", qua_vars=(I[i], Q[i]))
                            # wait for the resonator to deplete
                            rr.wait(rr.depletion_time * u.ns)
                            # save data
                            save(I[i], I_st[i])
                            save(Q[i], Q_st[i])
                align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                # Average the innermost n_avg shots, then buffer detuning then flux
                I_st[i].buffer(n_avg).map(FUNCTIONS.average()).buffer(len(dfs)).buffer(len(dcs)).save(f"I{i + 1}")
                Q_st[i].buffer(n_avg).map(FUNCTIONS.average()).buffer(len(dfs)).buffer(len(dcs)).save(f"Q{i + 1}")


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
                node.parameters.num_flux_points,
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
    """Fit the resonator dip flux-by-flux with scqat to reduce the 2-D map to a
    1-D centre-frequency(flux) trace. The per-qubit (slice, results) pairs are kept
    in the namespace so plot_data can redraw the figures without refitting."""
    ds = process_raw_dataset(node.results["ds_raw"], node)
    node.results["ds_raw"] = ds
    sep_results, fit_results = fit_raw_data(ds, node)
    node.namespace["sep_results"] = sep_results
    node.results["fit_results"] = fit_results

    # Log the per-slice (flux-by-flux) dip-fit summary
    log_fitted_results(node.results["fit_results"], log_callable=node.log)

    # Second stage: fit the centre-frequency(flux) trace with the full-transmon
    # dispersive model (sweet spot, dv_phi0, f_r0; g is conditional for now).
    dispersion_sep, dispersion_results = fit_flux_dependence(sep_results, node)
    node.namespace["dispersion_sep"] = dispersion_sep
    node.results["dispersion_results"] = dispersion_results
    log_dispersion_results(dispersion_results, log_callable=node.log)

    # The dispersive fit is the deliverable that gates the state update, so the
    # node outcome reflects its per-qubit success.
    node.outcomes = {
        qubit_name: ("successful" if disp["success"] else "failed")
        for qubit_name, disp in node.results["dispersion_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate or not node.parameters.plot)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """One combined figure per qubit: the 2-D |IQ| raw map, the per-flux fitted
    resonator centres, and the dispersive centre-frequency(flux) fit curve."""
    node.results["figures"] = plot_combined(
        node.namespace["sep_results"], node.namespace["dispersion_sep"]
    )
    plt.show()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Write the robust dispersive-fit outputs to the QUAM state: the idle
    (sweet-spot) flux offset, the minimum-frequency flux point, the resonator
    readout frequency at the sweet spot, and the flux period (phi0).

    Only the degeneracy-independent quantities are written; g / f_q_max stay out
    of the state (they are conditional until a spectroscopy prior is supplied).

    When a single external flux source drives the sweep (z_source_qubit set), only
    that qubit measures its own resonator-vs-its-own-flux; every other measured
    resonator is crosstalk from the source's flux line, so its z offsets / readout
    frequency must NOT be updated from this run."""
    z_src = node.parameters.z_source_qubit
    with node.record_state_updates():
        for q in node.namespace["qubits"]:
            if q.z is None or node.outcomes[q.name] == "failed":
                continue
            # Skip crosstalk qubits: only the flux-source qubit's fit is a valid
            # self-flux calibration (when z_source_qubit is None, every qubit fluxes
            # itself, so none are skipped).
            if z_src is not None and q.name != z_src:
                node.log(f"Skipping state update for {q.name}: crosstalk under z_source_qubit={z_src}")
                continue

            disp = node.results["dispersion_results"][q.name]

            # Idle (sweet-spot) flux offset — the flux of maximum resonator frequency.
            if q.z.flux_point == "independent":
                q.z.independent_offset = disp["sweet_spot_flux"]
            else:
                q.z.joint_offset = disp["sweet_spot_flux"]
            # Minimum-frequency flux point (half a period from the sweet spot).
            if node.parameters.update_flux_min:
                q.z.min_offset = disp["min_offset"]
            # Resonator readout frequency at the sweet spot (absolute).
            q.resonator.f_01 = disp["sweet_spot_freq"]
            q.resonator.RF_frequency = disp["sweet_spot_freq"]
            # Flux quantum in voltage / current.
            q.phi0_voltage = disp["dv_phi0"]
            q.phi0_current = disp["phi0_current"]


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
