"""Manual end-to-end run of the QM scqo experiments.

Defaults to scqo's SimulatedBackend so it runs with no OPX hardware (the simulated
backend uses each experiment's inherited ``simulate()`` and never calls ``probe``).
To run on the real OPX, swap in QMBackend (see the commented lines) - nothing else
changes.

    conda run -n LCHQM_test python scripts/run_ramsey_qm.py
"""

from __future__ import annotations

import json

from scqo import Session
from scqo.testing import InMemoryDevice, SimulatedBackend

import customized.scqo  # noqa: F401  registers QMQubitRamsey / QMQubitPowerRabi into the catalog


def main() -> None:
    device = InMemoryDevice(
        {
            "q4": {"readout_freq": 6.10e9, "drive_freq": 4.20e9, "pi_amp": 0.20},
            "q5": {"readout_freq": 6.20e9, "drive_freq": 4.35e9, "pi_amp": 0.18},
        }
    )
    backend = SimulatedBackend(device)
    # Real hardware instead:
    # from customized.scqo import QMBackend
    # backend = QMBackend.load(state_path=r"D:\github\LCHQMDriver\quam_state", timeout=120)

    sess = Session(backend)

    print("catalog:", [e["name"] for e in sess.catalog()])

    print("\ndrive_freq before:", {q: s["drive_freq"] for q, s in sess.device_state().items()})
    ramsey = sess.run("qubit_ramsey", {"qubits": ["q4", "q5"], "num_averages": 200})
    print("qubit_ramsey result:", json.dumps(ramsey, indent=2))
    print("drive_freq after: ", {q: s["drive_freq"] for q, s in sess.device_state().items()})

    print("\npi_amp before:", {q: s["pi_amp"] for q, s in sess.device_state().items()})
    rabi = sess.run("qubit_power_rabi", {"qubits": ["q4", "q5"], "num_averages": 200})
    print("qubit_power_rabi result:", json.dumps(rabi, indent=2))
    print("pi_amp after: ", {q: s["pi_amp"] for q, s in sess.device_state().items()})

    print("\nreadout_freq before:", {q: s["readout_freq"] for q, s in sess.device_state().items()})
    rspec = sess.run("resonator_spectroscopy", {"qubits": ["q4", "q5"], "num_averages": 200})
    print("resonator_spectroscopy result:", json.dumps(rspec, indent=2))
    print("readout_freq after: ", {q: s["readout_freq"] for q, s in sess.device_state().items()})


if __name__ == "__main__":
    main()
