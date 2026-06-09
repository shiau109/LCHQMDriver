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
from customized.node.LCH_qubit_spectroscopy import (
    Parameters,
    log_fitted_results,
)
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot
from qualibration_libs.data import XarrayDataFetcher


# %% {Node initialisation}
description = """
        If Drive Qubit is None, all qubits in Qubits are driven.
        Ask LCH
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_qubit_spectroscopy",  # Name should be unique
    description=description,  # Describe what the node is doing, which is also reflected in the QUAlibrate GUI
    parameters=Parameters(),  # Node parameters defined under quam_experiment/experiments/node_name
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    # You can get type hinting in your IDE by typing node.parameters.
    node.parameters.qubits = ["q1"]
    node.parameters.drive_qubit = ["q1"]
    node.parameters.simulate = True
    # pass


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

    operation = node.parameters.operation  # The qubit operation to play
    n_avg = node.parameters.num_shots  # The number of averages
    # Adjust the pulse duration and amplitude to drive the qubit into a mixed state - can be None
    operation_len = node.parameters.operation_len_in_ns
    # pre-factor to the value defined in the config - restricted to [-2; 2)
    operation_amp = node.parameters.operation_amplitude_factor
    # Qubit detuning sweep with respect to their resonance frequencies
    point_freq = node.parameters.num_frequency_points
    dfs = np.linspace(node.parameters.min_frequency_in_mhz* u.MHz, node.parameters.max_frequency_in_mhz* u.MHz, point_freq)
    # Register the sweep axes to be added to the dataset when fetching data
    node.namespace["sweep_axes"] = {
        "qubit": xr.DataArray(qubits.get_names()),
        "detuning": xr.DataArray(dfs, attrs={"long_name": "readout frequency", "units": "Hz"}),
    }

    with program() as node.namespace["qua_program"]:
        # Macro to declare I, Q, n and their respective streams for a given number of qubit
        I, I_st, Q, Q_st, n, n_st = node.machine.declare_qua_variables()
        df = declare(int)  # QUA variable for the qubit frequency

        for multiplexed_qubits in qubits.batch():
            # Initialize the QPU in terms of flux points (flux tunable transmons and/or tunable couplers)
            for qubit in multiplexed_qubits.values():
                node.machine.initialize_qpu(target=qubit)
            align()

            with for_(n, 0, n < n_avg, n + 1):
                save(n, n_st)
                with for_(*from_array(df, dfs)):                        
                    for i, qubit in multiplexed_qubits.items():
                        qubit.reset(
                            node.parameters.reset_type,
                            node.parameters.simulate,
                            log_callable=node.log,
                        )

                        # Update the qubit frequency
                    
                    for i, qubit in multiplexed_qubits.items():
                        
                        if node.parameters.drive_qubit is None:
                            # Get the duration of the operation from the node parameters or the state
                            duration = operation_len if operation_len is not None else qubit.xy.operations[operation].length
                            qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                            # Play the saturation pulse
                            qubit.xy.play(
                                operation,
                                amplitude_scale=operation_amp,
                                duration=duration // 4,
                            )
                        elif qubit.name == node.parameters.drive_qubit:
                            # Get the duration of the operation from the node parameters or the state
                            duration = operation_len if operation_len is not None else qubit.xy.operations[operation].length
                            qubit.xy.update_frequency(df + qubit.xy.intermediate_frequency)
                            # Play the saturation pulse
                            qubit.xy.play(
                                operation,
                                amplitude_scale=operation_amp,
                                duration=duration // 4,
                            )
                    align()

                    for i, qubit in multiplexed_qubits.items():
                        # readout the resonator
                        qubit.resonator.measure("readout", qua_vars=(I[i], Q[i]))
                        # save data
                        save(I[i], I_st[i])
                        save(Q[i], Q_st[i])
                    align()

        with stream_processing():
            n_st.save("n")
            for i in range(num_qubits):
                I_st[i].buffer(len(dfs)).average().save(f"I{i + 1}")
                Q_st[i].buffer(len(dfs)).average().save(f"Q{i + 1}")


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
    """Analyse the raw data with scqat's QubitSpectroscopyEstimator. ds_raw is enriched
    once into the canonical, estimator-native form (I/Q + detuning + full_freq); the
    estimator builds IQdata from I/Q and fits the qubit line (peak detuning + FWHM). The
    QM-specific write-backs are then derived (readout integration-weight angle; saturation /
    x180 amplitudes from the fitted FWHM). Per-qubit (dataset, results, plot_data) triples
    are kept in the namespace so plot_data redraws without refitting, and an offline re-fit
    reads the same ds_raw with no prep."""
    from scqat.parsers import repetition_data
    from scqat.estimators.qubit_spectroscopy import QubitSpectroscopyEstimator
    from quam_config.instrument_limits import instrument_limits

    # Make ds_raw the canonical, estimator-native input: enrich it once with the absolute
    # drive-frequency axis (the only QUAM-dependent piece). I/Q stay float (netCDF-safe) and
    # the estimator builds IQdata from them, so both the live run and an offline re-fit read
    # this same ds_raw via repetition_data -> analyze with no per-slice prep.
    ds = node.results["ds_raw"]
    if "full_freq" not in ds.coords:
        rf = {q.name: q.xy.RF_frequency for q in node.namespace["qubits"]}
        full_freq = ds.detuning.values[None, :] + np.array(
            [rf[str(n)] for n in ds.qubit.values]
        )[:, None]
        ds = ds.assign_coords(full_freq=(("qubit", "detuning"), full_freq))
        node.results["ds_raw"] = ds

    estimator = QubitSpectroscopyEstimator()
    node.namespace["estimator"] = estimator
    node.namespace["sep_results"] = {}
    node.results["fit_results"] = {}

    op_amp_factor = node.parameters.operation_amplitude_factor
    span_hz = abs(node.parameters.max_frequency_in_mhz - node.parameters.min_frequency_in_mhz) * 1e6

    for sq in repetition_data(ds, repetition_dim="qubit"):
        qubit_name = sq["qubit"].values.item()
        q = next(x for x in node.namespace["qubits"] if x.name == qubit_name)
        limits = instrument_limits(q.xy)

        # sq already carries I/Q + detuning + full_freq (from ds_raw); the estimator builds
        # IQdata from I/Q. Keep up to node.parameters.max_peaks lines (SNR-gated, so fewer are
        # returned when fewer are real); the write-back below picks the largest-area one.
        results = estimator.analyze(
            sq, output_dir=None, skip_figures=True, max_peaks=node.parameters.max_peaks,
        )[0]
        # Build the plot-data once (the estimator-native reconstruction Dataset): reused for the
        # figure (plot_data run-action) and, when save_plot_data is set, persisted as
        # plotdata_<qubit>.h5 — reloadable via load_xarray_h5 + generate_figures(plot_data=...).
        plot_data = estimator.build_plot_data(sq, results)
        node.namespace["sep_results"][qubit_name] = (sq, results, plot_data)
        if node.parameters.save_plot_data:
            node.results[f"plotdata_{qubit_name}"] = plot_data

        peaks = results.get("peaks", [])
        if peaks:
            # Pick the line with the largest Lorentzian area (∝ |amplitude|·fwhm) — a more
            # robust "main transition" criterion than peak height when several lines appear.
            peak = max(peaks, key=lambda p: abs(p["amplitude"]) * p["fwhm"])
            detuning = float(peak["detuning"])
            fwhm = float(peak["fwhm"])
            frequency = float(peak.get("full_freq", detuning + q.xy.RF_frequency))
            fit_ok = bool(np.isfinite(frequency) and np.isfinite(fwhm) and fwhm > 0)
        else:
            peak = None
            detuning = fwhm = frequency = float("nan")
            fit_ok = False

        # Readout integration-weight angle: rotate so the qubit-induced IQ shift lands on
        # the I axis, evaluated at the fitted peak detuning (was: detuning of max |IQ_abs|).
        if fit_ok:
            at_peak = sq.sel(detuning=detuning, method="nearest")
            d_angle = float(np.arctan2(
                at_peak.Q - sq.Q.mean("detuning"),
                at_peak.I - sq.I.mean("detuning"),
            ))
        else:
            d_angle = 0.0
        prev_angle = q.resonator.operations["readout"].integration_weights_angle
        iw_angle = float((prev_angle + d_angle) % (2 * np.pi))

        # Saturation / x180 amplitudes derived from the fitted FWHM (unchanged formulas).
        used_amp = q.xy.operations["saturation"].amplitude * op_amp_factor
        x180_length = q.xy.operations["x180"].length * 1e-9
        if fit_ok:
            saturation_amp = float(node.parameters.target_peak_width / fwhm * used_amp / op_amp_factor)
            x180_amp = float(np.pi / (fwhm * x180_length) * used_amp)
        else:
            saturation_amp = x180_amp = float("nan")

        # Success criteria preserved from the original node.
        rf = q.xy.RF_frequency
        freq_success = abs(frequency) < span_hz + rf
        fwhm_success = abs(fwhm) < span_hz + rf
        sat_success = abs(saturation_amp) < limits.max_wf_amplitude
        success = bool(fit_ok and freq_success and fwhm_success and sat_success)

        node.results["fit_results"][qubit_name] = {
            "frequency": frequency,
            "fwhm": fwhm,
            "iw_angle": iw_angle,
            "saturation_amp": saturation_amp,
            "x180_amp": x180_amp,
            "success": success,
            # All detected peaks (estimator's detuning order, so indices match the figure's
            # `peak` axis); is_primary marks the largest-area line used for the write-back.
            "peaks": [
                {
                    "detuning": float(p["detuning"]),
                    "full_freq": float(p.get("full_freq", p["detuning"] + q.xy.RF_frequency)),
                    "amplitude": float(p["amplitude"]),
                    "fwhm": float(p["fwhm"]),
                    "area": float(np.pi / 2 * abs(p["amplitude"]) * p["fwhm"]),
                    "is_primary": p is peak,
                }
                for p in peaks
            ],
        }

    # Log the relevant information extracted from the data analysis
    log_fitted_results(node.results["fit_results"], log_callable=node.log)
    node.outcomes = {
        qubit_name: ("successful" if fit_result["success"] else "failed")
        for qubit_name, fit_result in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate or not node.parameters.plot)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Redraw the scqat qubit-spectroscopy figure for each qubit from the stored
    (dataset, results, plot_data) triples (no refit, no rebuild) and store them in
    node.results["figures"]."""
    estimator = node.namespace["estimator"]
    node.results["figures"] = {}
    for qubit_name, (sq, results, plot_data) in node.namespace["sep_results"].items():
        node.results["figures"][qubit_name] = estimator.generate_figures(
            sq, results, plot_data=plot_data
        )
    plt.show()


# %% {Update_state}
@node.run_action(skip_if=node.parameters.simulate)
def update_state(node: QualibrationNode[Parameters, Quam]):
    """Update the relevant parameters if the qubit data analysis was successful."""
    with node.record_state_updates():
        for q in node.namespace["qubits"]:
            if node.outcomes[q.name] == "failed":
                continue

            # Update the readout frequency for the given flux point
            q.f_01 = node.results["fit_results"][q.name]["frequency"]
            q.xy.RF_frequency = node.results["fit_results"][q.name]["frequency"]

            fit_result = node.results["fit_results"][q.name]
            # Update the integration weight angle
            q.resonator.operations["readout"].integration_weights_angle = fit_result["iw_angle"]
            if node.parameters.update_pulses_amplitude:
                # Update the saturation amplitude
                q.xy.operations["saturation"].amplitude = fit_result["saturation_amp"]
                # Update the x180 and x90 amplitudes
                q.xy.operations["x180"].amplitude = fit_result["x180_amp"]
                q.xy.operations["x90"].amplitude = fit_result["x180_amp"] / 2


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
