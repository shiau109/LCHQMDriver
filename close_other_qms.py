"""Close all active Quantum Machines (QMs) on the OPX controller.

Usage from PowerShell / Terminal:
    python C:\Users\ASUS\Documents\GitHub\LCHQMDriver\close_other_qms.py

Usage in Python code:
    from customized.probes.qubit_tomography import close_other_qms  # or import directly
    close_other_qms()
"""

import sys
from quam_config import Quam


def close_other_qms() -> None:
    """Connects to OPX via QUAM and closes all active Quantum Machine instances."""
    try:
        machine = Quam.load()
        qmm = machine.connect()
        qmm.close_all_qms()
        print("[SUCCESS] Closed all active Quantum Machines on OPX.")
    except Exception as e:
        print(f"[ERROR] Failed to close Quantum Machines: {e}")
        # Fallback to direct QuantumMachinesManager
        try:
            from qm.quantum_machines_manager import QuantumMachinesManager
            qmm = QuantumMachinesManager(host="192.168.88.10", port=80)
            qmm.close_all_qms()
            print("[SUCCESS] Closed all active Quantum Machines via fallback manager.")
        except Exception as e2:
            print(f"[ERROR] Fallback failed as well: {e2}")


if __name__ == "__main__":
    close_other_qms()
