# %% {Imports}
import numpy as np

from qualibrate import QualibrationNode
from quam_config import Quam
from customized.node.LCH_qc_N_swap import Parameters, analysis
from qualibration_libs.parameters import get_qubits
from qualibration_libs.runtime import simulate_and_plot

from customized.probes import qc_N_swap as probe


# %% {Description}
description = """
        N-SWAP (SWAP-CHAIN) CIRCUIT (customized)
Exercises a coherent swap chain. Each shot prepares an excitation on the swap pair's
control qubit (x180), then applies a SWAP on the qubit pair (`swap_pair.macros[swap_operation]`)
N times. The number of swaps N is swept, and the selected `qubits` (the measured set) are
read out at the end, giving one population-vs-N curve per measured qubit (N=0 is the no-swap
baseline). With a coherent iSWAP, population is exchanged back and forth between the pair
swap by swap.

The swap macro is invoked bare (`.apply()` with no extra args), so the chosen macro must be
callable that way (its amplitudes/pulses baked into the QUAM macro definition). Analysis fits
each measured qubit's population-vs-N curve with a cosine (scqat SwapOscillationEstimator),
extracting the swap-oscillation frequency f (cycles per swap) and swap_period = 1/f; the
outcome is gated on fit success. There is still no state writeback.

This node is a thin qualibrate shell: the acquisition probe lives in
`customized.probes.qc_N_swap`; the estimate adapter lives in
`customized.node.LCH_qc_N_swap`.
"""


# Be sure to include [Parameters, Quam] so the node has proper type hinting
node = QualibrationNode[Parameters, Quam](
    name="LCH_qc_N_swap",
    description=description,
    parameters=Parameters(),
)


# Any parameters that should change for debugging purposes only should go in here
# These parameters are ignored when run through the GUI or as part of a graph
@node.run_action(skip_if=node.modes.external)
def custom_param(node: QualibrationNode[Parameters, Quam]):
    """Allow the user to locally set the node parameters for debugging purposes, or execution in the Python IDE."""
    node.parameters.qubits = ["q2", "q3"]
    node.parameters.swap_pair = "q2_q3"
    node.parameters.swap_operation = "iswap"
    node.parameters.min_rounds = 0
    node.parameters.max_rounds = 10
    node.parameters.rounds_step = 1
    node.parameters.simulate = False
    node.parameters.num_shots = 1000
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

    (
        node.namespace["qua_program"],
        node.namespace["sweep_axes"],
    ) = probe.build_program(
        node.machine,
        list(qubits),
        swap_pair,
        swap_operation=p.swap_operation,
        rounds_array=rounds_array,
        num_shots=p.num_shots,
        reset_type=p.reset_type,
        use_state_discrimination=p.use_state_discrimination,
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
    """estimate: fit each measured qubit's swap oscillation with scqat (via the core)."""
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
    """Figures are produced by the scqat estimator in analyse_data."""
    pass


# %% {Save_results}
@node.run_action()
def save_results(node: QualibrationNode[Parameters, Quam]):
    node.save()
