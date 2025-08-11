from typing import Optional
from qualibrate.parameters import RunnableParameters


class CommonFluxParameters(RunnableParameters):
    """Common parameters for configuring a flux control node in a quantum machine simulation or execution."""

    flux_idle_case: str = "joint"
    """Flux point to control. Default is 'joint'."""
    