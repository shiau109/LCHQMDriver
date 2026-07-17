import numpy as np
import xarray as xr
from typing import Tuple, Dict
from qualibrate import QualibrationNode


def process_raw_dataset(ds: xr.Dataset, node: QualibrationNode) -> xr.Dataset:
    qubits = node.namespace["qubits"].get_names()
    n_train_shots = node.parameters.num_training_shots
    reps = node.parameters.num_shots
    gate_counts = node.parameters.gate_counts
    symmetrized = node.parameters.symmetrized_readout
    n_sym = 2 if symmetrized else 1
    
    basis_coords = ["x", "y", "z"]
    sym_coords = ["reg", "inv"] if symmetrized else ["reg"]
    gate_count_coords = np.array(gate_counts)
    
    i_tomo_all, q_tomo_all = [], []
    i_train_all, q_train_all = [], []
    
    for idx, q_name in enumerate(qubits):
        q_idx = idx + 1
        # 1. Training data
        i_g = ds[f"Ig{q_idx}"].values
        q_g = ds[f"Qg{q_idx}"].values
        i_e = ds[f"Ie{q_idx}"].values
        q_e = ds[f"Qe{q_idx}"].values
        
        i_train = np.stack([i_g, i_e], axis=0)
        q_train = np.stack([q_g, q_e], axis=0)
        
        i_train_all.append(i_train)
        q_train_all.append(q_train)
        
        # 2. Tomography data
        # raw shape: (n_runs, gate_count, basis, sym)
        # We need to transpose to ("basis", "sym", "gate_count", "n_runs")
        i_t = ds[f"I_tomo{q_idx}"].transpose("basis", "sym", "gate_count", "n_runs").values
        q_t = ds[f"Q_tomo{q_idx}"].transpose("basis", "sym", "gate_count", "n_runs").values
        
        i_tomo_all.append(i_t)
        q_tomo_all.append(q_t)
        
    return xr.Dataset(
        {
            "I_tomo": (("qubit", "basis", "sym", "gate_count", "shot_idx"), np.stack(i_tomo_all)),
            "Q_tomo": (("qubit", "basis", "sym", "gate_count", "shot_idx"), np.stack(q_tomo_all)),
            "I_train": (("qubit", "prepared_state", "train_shot_idx"), np.stack(i_train_all)),
            "Q_train": (("qubit", "prepared_state", "train_shot_idx"), np.stack(q_train_all)),
        },
        coords={
            "qubit": qubits,
            "basis": np.array(basis_coords),
            "sym": np.array(sym_coords),
            "gate_count": gate_count_coords,
            "shot_idx": np.arange(reps),
            "prepared_state": np.array([0, 1]),
            "train_shot_idx": np.arange(n_train_shots),
        }
    )


def fit_raw_data(ds: xr.Dataset, node: QualibrationNode) -> Tuple[xr.Dataset, dict[str, dict]]:
    from scqat.estimators.qubit_tomography import QubitTomographyEstimator
    
    estimator = QubitTomographyEstimator()
    fit_results = {}
    
    qubits = ds.coords["qubit"].values
    for qubit in qubits:
        q_slice = ds.sel(qubit=qubit)
        res = estimator.extract_parameters(q_slice)
        fit_results[qubit] = res
        
    return ds, fit_results


def log_fitted_results(fit_results: Dict, log_callable=None):
    import logging
    if log_callable is None:
        log_callable = logging.getLogger(__name__).info
    for q in fit_results.keys():
        res = fit_results[q]
        s_qubit = f"Results for qubit {q}: "
        s_fidelity = f"\tReadout fidelity: {res['readout_fidelity']:.3f} | "
        if res["success"]:
            s_qubit += " SUCCESS!\n"
        else:
            s_qubit += " FAIL!\n"
        log_callable(s_qubit + s_fidelity)
