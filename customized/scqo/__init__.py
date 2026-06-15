"""Optional scqo integration for the Quantum Machines backend.

Importing this package wires the QM stack into scqo: it exposes :class:`QMBackend`
and, as an import side effect, registers the QM experiments (`ramsey`,
`power_rabi`) into the scqo catalog.

This package requires `scqo` installed, and `qm`/`quam` for any real acquisition
(the vendor imports are lazy, so `import customized.scqo` itself stays light and
offline-friendly). It is NEVER imported by the qualibrate calibration nodes, which
keeps the qualibrate path independent of scqo.
"""

from customized.scqo.backend import QMBackend, QMDeviceModel, QMQubitView
from customized.scqo import experiments  # noqa: F401  (import side effect: @register)

__all__ = ["QMBackend", "QMDeviceModel", "QMQubitView"]
