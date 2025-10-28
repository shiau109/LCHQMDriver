
from quam_builder.architecture.superconducting.qubit import FluxTunableTransmon
from quam.core import quam_dataclass


__all__ = ["ChargeSensitiveTransmon"]
@quam_dataclass
class ChargeSensitiveTransmon(FluxTunableTransmon):
    """
    Example QUAM component for a flux tunable transmon qubit.

    Args:
        charge_dispersion (charge bias): .

    """

    charge_dispersion: float = 0.0