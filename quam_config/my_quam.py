from quam_builder.architecture.superconducting.qpu import FixedFrequencyQuam, FluxTunableQuam

from typing import Dict, Union, ClassVar, Type
from dataclasses import field



from customized.qubit_pair import LCH_FluxTunableTransmonQCQPair

from quam.core import quam_dataclass

from quam_builder.architecture.superconducting.qubit.fixed_frequency_transmon import (
    FixedFrequencyTransmon,
)

from customized.quam_builder.architecture.superconducting.qubit.charge_tunable_transmon import ChargeTunableTransmon




# Define the QUAM class that will be used in all calibration nodes
# Should inherit from either FixedFrequencyQuam or FluxTunableQuam
class Quam(FluxTunableQuam):
    # pass
    qubit_type: ClassVar[Type[ChargeTunableTransmon]] = ChargeTunableTransmon
    qubits: Dict[str, ChargeTunableTransmon] = field(default_factory=dict)

    # qubit_pair_type: ClassVar[Type[LCH_FluxTunableTransmonQCQPair]] = LCH_FluxTunableTransmonQCQPair
    # qubit_pairs: Dict[str, LCH_FluxTunableTransmonQCQPair] = field(default_factory=dict)