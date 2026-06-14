"""One-off: make RF_frequency a literal in quam_state (match state_lib).

Per qubit xy + resonator MW channel, swap:
  RF_frequency: "#./inferred_RF_frequency"  -> literal (= LO + IF, computed by quam)
  intermediate_frequency: <literal>         -> "#./inferred_intermediate_frequency"
Lets `q.resonator.RF_frequency = <freq>` work, while keeping IF = RF - LO consistent.
"""
import os
os.environ["QUAM_STATE_PATH"] = r"D:\github\LCHQMDriver\quam_state"

from quam_config import Quam

machine = Quam.load()

for qname, q in machine.qubits.items():
    for ch_name in ("xy", "resonator"):
        ch = getattr(q, ch_name, None)
        if ch is None:
            continue
        rf = float(ch.RF_frequency)            # quam resolves inferred = LO + IF
        ch.RF_frequency = None                 # clear the reference
        ch.RF_frequency = rf                   # store as a literal
        ch.intermediate_frequency = "#./inferred_intermediate_frequency"
        print(f"{qname}.{ch_name}: RF_frequency = {rf}")

machine.save()
print("saved ->", os.environ["QUAM_STATE_PATH"])
