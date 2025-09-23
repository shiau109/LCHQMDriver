from qm import generate_qua_script

qmm = QuantumMachinesManager(...)  # Optional - Used for config validation

config = {}

with program() as prog:
    ...

sourceFile = open('debug.py', 'w')
print(generate_qua_script(prog, config), file=sourceFile) 
sourceFile.close()