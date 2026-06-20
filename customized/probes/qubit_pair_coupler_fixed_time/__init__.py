"""Fixed-time qubit-flux x coupler-flux probe (acquisition only). See package docstring
of `customized.probes` for the import rules."""

from customized.probes.qubit_pair_coupler_fixed_time.probe import acquire, build_program

__all__ = ["build_program", "acquire"]
