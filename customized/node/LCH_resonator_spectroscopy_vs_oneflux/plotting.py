"""Plotting wrapper for the LCH_resonator_spectroscopy_vs_oneflux node.

Delegates to the scqat ``ResonatorSpectroscopyVsFluxAnalyzer`` to redraw, for
each qubit, the 2-D ``|IQ|`` amplitude map over (flux, frequency) with the
fitted resonator-centre trace overlaid — one figure per qubit, like the
LCH_resonator_spectroscopy node.
"""

from typing import Dict


def plot_raw_data_with_fit(sep_results: Dict, qubits=None) -> Dict:
    """Redraw the scqat vs-flux figure for every qubit from the stored
    ``(slice_ds, analyzer_results)`` pairs produced by ``fit_raw_data``.

    Parameters
    ----------
    sep_results : dict
        ``{qubit_name: (slice_ds, analyzer_results)}`` from ``fit_raw_data``.
    qubits : optional
        Unused; accepted for signature parity with the official plotting helper.

    Returns
    -------
    dict
        ``{qubit_name: {figure_name: matplotlib.figure.Figure}}``.
    """
    from scqat.protocols.resonator_spectroscopy_vs_flux import ResonatorSpectroscopyVsFluxAnalyzer

    analyzer = ResonatorSpectroscopyVsFluxAnalyzer()
    figures: Dict = {}
    for qubit_name, (sq, results) in sep_results.items():
        figures[qubit_name] = analyzer.generate_figures(sq, results)
    return figures


def plot_flux_dispersion(dispersion_sep: Dict) -> Dict:
    """Redraw the dispersive flux-dependence figure for every qubit from the
    stored ``(trace_ds, analyzer_results)`` pairs produced by ``fit_flux_dependence``.

    Parameters
    ----------
    dispersion_sep : dict
        ``{qubit_name: (trace_ds, analyzer_results)}`` from ``fit_flux_dependence``.

    Returns
    -------
    dict
        ``{qubit_name: {figure_name: matplotlib.figure.Figure}}``.
    """
    from scqat.protocols.resonator_flux_dispersion import ResonatorFluxDispersionAnalyzer

    analyzer = ResonatorFluxDispersionAnalyzer()
    figures: Dict = {}
    for qubit_name, (trace, res) in dispersion_sep.items():
        figures[qubit_name] = analyzer.generate_figures(trace, res)
    return figures
