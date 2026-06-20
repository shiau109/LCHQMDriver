"""Time-dependent readout-resonator photon probe (acquisition only). See package
docstring of `customized.probes` for the import rules."""

from customized.probes.qubit_acstark_time.probe import acquire, build_program

__all__ = ["build_program", "acquire"]
