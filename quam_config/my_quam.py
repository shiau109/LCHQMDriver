from quam_builder.architecture.superconducting.qpu import FixedFrequencyQuam, FluxTunableQuam

from typing import Dict, Union, ClassVar, Type
from dataclasses import field



from customized.qubit_pair import LCH_FluxTunableTransmonQCQPair



# Define the QUAM class that will be used in all calibration nodes
# Should inherit from either FixedFrequencyQuam or FluxTunableQuam
class Quam(FluxTunableQuam):
    pass
    # qubit_pair_type: ClassVar[Type[LCH_FluxTunableTransmonQCQPair]] = LCH_FluxTunableTransmonQCQPair
    # qubit_pairs: Dict[str, LCH_FluxTunableTransmonQCQPair] = field(default_factory=dict)