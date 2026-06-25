"""N-swap (swap-chain) circuit probe (acquisition only). See package docstring of
`customized.probes` for the import rules."""

from customized.probes.qc_N_swap.probe import acquire, build_program

__all__ = ["build_program", "acquire"]
