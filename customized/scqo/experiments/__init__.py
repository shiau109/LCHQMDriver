"""Importing this package registers every QM experiment into the scqo catalog.

Add a line here for each new experiment module so its ``@register`` runs.
"""

from . import qubit_echo  # noqa: F401  (import side effect: @register)
from . import qubit_power_rabi  # noqa: F401  (import side effect: @register)
from . import qubit_ramsey  # noqa: F401  (import side effect: @register)
from . import qubit_relaxation  # noqa: F401  (import side effect: @register)
from . import qubit_spectroscopy  # noqa: F401  (import side effect: @register)
from . import qubit_spectroscopy_flux  # noqa: F401  (import side effect: @register)
from . import readout_frequency  # noqa: F401  (import side effect: @register)
from . import readout_power  # noqa: F401  (import side effect: @register)
from . import resonator_spectroscopy  # noqa: F401  (import side effect: @register)
from . import resonator_spectroscopy_flux  # noqa: F401  (import side effect: @register)
from . import resonator_spectroscopy_power_chain  # noqa: F401  (import side effect: @register)
from . import resonator_spectroscopy_power_amp  # noqa: F401  (import side effect: @register)
from . import single_shot_readout  # noqa: F401  (import side effect: @register)
from . import qubit_tomography  # noqa: F401  (import side effect: @register)
from . import qubit_sqrb  # noqa: F401  (import side effect: @register)
from . import qubit_relaxation_flux  # noqa: F401  (import side effect: @register)
from . import qubit_echo_flux  # noqa: F401  (import side effect: @register)
from . import qubit_drag_equator  # noqa: F401  (import side effect: @register)
from . import qubit_drag_alternating  # noqa: F401  (import side effect: @register)

__all__ = ["qubit_ramsey", "qubit_spectroscopy", "qubit_power_rabi", "resonator_spectroscopy", "qubit_tomography", "qubit_sqrb", "qubit_relaxation_flux", "qubit_echo_flux", "qubit_drag_equator", "qubit_drag_alternating"]


