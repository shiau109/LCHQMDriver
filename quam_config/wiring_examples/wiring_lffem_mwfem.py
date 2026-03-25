import matplotlib.pyplot as plt
from qualang_tools.wirer.wirer.channel_specs import *
from qualang_tools.wirer import Instruments, Connectivity, allocate_wiring, visualize
from quam_builder.builder.qop_connectivity import build_quam_wiring
from quam_builder.builder.superconducting import build_quam
from quam_config import Quam

########################################################################################################################
# %%                                              Define static parameters
########################################################################################################################
host_ip = "10.21.30.201"  # QOP IP address
port = 9516  # QOP Port
cluster_name = "QPX1000_6"  # Name of the cluster

########################################################################################################################
# %%                                      Define the available instrument setup
########################################################################################################################
instruments = Instruments()
instruments.add_mw_fem(controller=1, slots=[7])
# instruments.add_lf_fem(controller=1, slots=[3, 5])

########################################################################################################################
# %%                                 Define which qubit ids are present in the system
########################################################################################################################
qubits = [1]
# qubit_pairs = [(qubits[i], qubits[i + 1]) for i in range(len(qubits) - 1)]

########################################################################################################################
# %%                                 Define any custom/hardcoded channel addresses
########################################################################################################################
# multiplexed readout for qubits 1 to 4 and 5 to 8 on two feed-lines
q1to4_res_ch = mw_fem_spec(con=1, slot=7, in_port=1, out_port=1)
# q5to8_res_ch = mw_fem_spec(con=1, slot=2, in_port=1, out_port=1)
# Q1 slot 7, port 2
# Q2 slot 7, port 3
# RO slot 7, port 1
# individual xy drive for qubits 1 to 4 on MW-FEM 1
q1_drive_ch = mw_fem_spec(con=1, slot=7, out_port=2)
# multiplexed xy drive for qubits 5 to 8 on MW-FEM 2 port 4
# q2_drive_ch = mw_fem_spec(con=1, slot=7, out_port=3)

########################################################################################################################
# %%                Allocate the wiring to the connectivity object based on the available instruments
########################################################################################################################
connectivity = Connectivity()
# The readout lines
connectivity.add_resonator_line(qubits=qubits, constraints=q1to4_res_ch)
# The xy drive lines
connectivity.add_qubit_drive_lines(qubits=qubits[0], constraints=q1_drive_ch)
# connectivity.add_qubit_drive_lines(qubits=qubits[1], constraints=q2_drive_ch)

# for qubit in qubits[4:]:
#     connectivity.add_qubit_drive_lines(qubits=qubit, constraints=q5to8_drive_ch)
#     allocate_wiring(connectivity, instruments, block_used_channels=False)
# The flux lines for the individual qubits
# connectivity.add_qubit_flux_lines(qubits=qubits)
# The flux lines for the tunable couplers
# connectivity.add_qubit_pair_flux_lines(qubit_pairs=qubit_pairs)
# Allocate the wiring
allocate_wiring(connectivity, instruments)

# View wiring schematic
visualize(connectivity.elements, available_channels=instruments.available_channels)
plt.show(block=False)

########################################################################################################################
# %%                                   Build the wiring and QUAM
########################################################################################################################
user_input = input("Do you want to save the updated QUAM? (y/n)")
if user_input.lower() == "y":
    machine = Quam()
    # Build the wiring (wiring.json) and initiate the QUAM
    build_quam_wiring(connectivity, host_ip, cluster_name, machine)

    # Reload QUAM, build the QUAM object and save the state as state.json
    machine = Quam.load()
    build_quam(machine)
