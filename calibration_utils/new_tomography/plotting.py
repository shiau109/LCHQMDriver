import xarray as xr
from scqat.estimators.qubit_tomography import QubitTomographyEstimator


def plot_raw_data_with_fit(ds: xr.Dataset, qubits: list, fit_results: dict) -> dict:
    estimator = QubitTomographyEstimator()
    figs = {}
    
    qubit_names = [q if isinstance(q, str) else q.name for q in qubits]
    
    for q_name in qubit_names:
        res = fit_results[q_name]
        q_slice = ds.sel(qubit=q_name)
        plot_data = estimator.build_plot_data(q_slice, res)
        q_figs = estimator.generate_figures(q_slice, res, plot_data)
        
        for fig_name, fig in q_figs.items():
            figs[f"{q_name}_{fig_name}"] = fig
            
    return figs
