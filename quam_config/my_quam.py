from quam_builder.architecture.superconducting.qpu import FixedFrequencyQuam, FluxTunableQuam

from quam_builder.architecture.superconducting.qubit_pair import FluxTunableTransmonPair
from typing import Dict, Union, ClassVar, Type
from dataclasses import field



from quam_builder.architecture.superconducting.components.tunable_coupler import (
    TunableCoupler,
)


# class LCH_TunableCoupler(TunableCoupler):

# Define the QUAM class that will be used in all calibration nodes
# Should inherit from either FixedFrequencyQuam or FluxTunableQuam
class Quam(FluxTunableQuam):
    qubit_pair_type: ClassVar[Type[FluxTunableTransmonPair]] = FluxTunableTransmonPair
    qubit_pairs: Dict[str, FluxTunableTransmonPair] = field(default_factory=dict)