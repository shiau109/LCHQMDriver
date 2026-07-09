# %% {Imports}
import numpy as np

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_qc_N_swap_amp import Parameters, analysis
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot

from customized.probes import qc_N_swap_amp as probe


# %% {Description}
description = """
        N-SWAP x QUBIT-FLUX-AMPLITUDE 2D SWEEP (customized)
A 2D variant of LCH_qc_N_swap: on top of the swap-count sweep N (inner axis), the swap
macro's control-qubit flux amplitude is swept (outer axis) -- the same knob
LCH_pair_qcq_fixed_time sweeps in its swap_via_macro mode. Each shot prepares an
excitation on the swap pair's control qubit (x180), then applies the SWAP
(`swap_pair.macros[swap_operation].apply(ctrl_amp=a)`) N times, every swap at the swept
amplitude a in ABSOLUTE VOLTS (the macro rescales its z flux pulse; the coupler plays
bare at its baked amplitude). The selected `qubits` (the measured set) are read out at
the end, giving one 2D population map (N x amplitude) per measured qubit -- a
swap-amplitude fine-tuning map by error amplification (N=0 is the no-swap baseline).

Analysis fits each qubit's population-vs-N curve at EVERY amplitude with a cosine (scqat
SwapOscillationEstimator), extracting the swap-oscillation frequency f (cycles per swap)
and contrast versus amplitude; `best_amplitude` (the successful row with the largest
contrast -- the resonance indicator, since a detuned swap oscillates faster but
shallower) is reported for inspection only. The outcome is gated on at least one row
fitting; there is still no state writeback.

This node is a thin qualibrate shell: the acquisition probe lives in
`customized.probes.qc_N_swap_amp`; the estimate adapter and plot live in
`customized.node.LCH_qc_N_swap_amp`.
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_qc_N_swap_amp",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    node.parameters.qubits = ["q1", "q2"]
    node.parameters.swap_pair = "q1_q2"
    node.parameters.swap_operation = "iswap"
    node.parameters.min_rounds = 0
    node.parameters.max_rounds = 20
    node.parameters.rounds_step = 1
    node.parameters.qubit_amp_start = 0.150
    node.parameters.qubit_amp_end = 0.155
    node.parameters.qubit_amp_step = 0.0002
    node.parameters.simulate = False
    node.parameters.num_shots = 100
    node.parameters.use_state_discrimination = True
    # operation_gap_ns idles the pair's flux lines between swaps so each swap's flux
    # can settle before the next one fires (0 = no gap).
    node.parameters.operation_gap_ns = 16
    pass


# Instantiate the QUAM class from the state file
node.machine = Quam.load()


# %% {Create_QUA_program}
@node.run_action(skip_if=node.parameters.load_data_id is not None)
def create_qua_program(node: QualibrationNode[Parameters, Quam]):
    """probe (build half): create the sweep axes and the QUA program via the probe."""
    p = node.parameters
    # The MEASURED set read out at the end of the circuit.
    node.namespace["qubits"] = qubits = get_qubits(node)
    # The swap pair is a single named target.
    swap_pair = node.machine.qubit_pairs[p.swap_pair]
    # Swap-count sweep (inclusive of max_rounds; 0 is the no-swap baseline).
    rounds_array = np.arange(p.min_rounds, p.max_rounds + 1, p.rounds_step)
    # Ctrl flux amplitude sweep in absolute volts (the macro's ctrl_amp).
    qubit_amplitudes = np.arange(p.qubit_amp_start, p.qubit_amp_end, p.qubit_amp_step)

    (
        node.namespace["qua_program"],
        node.namespace["sweep_axes"],
    ) = probe.build_program(
        node.machine,
        list(qubits),
        swap_pair,
        swap_operation=p.swap_operation,
        rounds_array=rounds_array,
        qubit_amplitudes=qubit_amplitudes,
        num_shots=p.num_shots,
        reset_type=p.reset_type,
        use_state_discrimination=p.use_state_discrimination,
        operation_gap_ns=p.operation_gap_ns,
        simulate=p.simulate,
    )


# %% {Simulate}
@node.run_action(skip_if=node.parameters.load_data_id is not None or not node.parameters.simulate)
def simulate_qua_program(node: QualibrationNode[Parameters, Quam]):
    """Connect to the QOP and simulate the QUA program"""
    qmm = node.machine.connect()
    config = node.machine.generate_config()
    samples, fig, wf_report = simulate_and_plot(qmm, config, node.namespace["qua_program"], node.parameters)
    node.results["simulation"] = {"figure": fig, "wf_report": wf_report, "samples": samples}


# %% {Execute}
@node.run_action(skip_if=node.parameters.load_data_id is not None or node.parameters.simulate)
def execute_qua_program(node: QualibrationNode[Parameters, Quam]):
    """probe (run half): execute on the QOP and store the raw dataset as "ds_raw"."""
    node.results["ds_raw"] = probe.acquire(
        node.machine,
        node.namespace["qua_program"],
        node.namespace["sweep_axes"],
        num_shots=node.parameters.num_shots,
        timeout=node.parameters.timeout,
        log=node.log,
    )


# %% {Load_historical_data}
@node.run_action(skip_if=node.parameters.load_data_id is None)
def load_data(node: QualibrationNode[Parameters, Quam]):
    """Load a previously acquired dataset."""
    load_data_id = node.parameters.load_data_id
    node.load_from_id(node.parameters.load_data_id)
    node.parameters.load_data_id = load_data_id
    node.namespace["qubits"] = get_qubits(node)


# %% {Analyse_data}
@node.run_action(skip_if=node.parameters.simulate)
def analyse_data(node: QualibrationNode[Parameters, Quam]):
    """estimate: fit each qubit's swap oscillation at every amplitude with scqat (via the core)."""
    node.results["fit_results"], node.results["figures"] = analysis.fit(
        node.results["ds_raw"],
        use_state_discrimination=node.parameters.use_state_discrimination,
    )
    node.outcomes = {
        qubit_name: ("successful" if fit_result["success"] else "failed")
        for qubit_name, fit_result in node.results["fit_results"].items()
    }


# %% {Plot_data}
@node.run_action(skip_if=node.parameters.simulate)
def plot_data(node: QualibrationNode[Parameters, Quam]):
    """Figures are produced by the scqat-based adapter in analyse_data."""
    pass


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
