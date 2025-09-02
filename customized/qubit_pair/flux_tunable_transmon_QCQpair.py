from quam_builder.architecture.superconducting.qubit_pair import FluxTunableTransmonPair


__all__ = ["LCH_FluxTunableTransmonQCQPair"]

class LCH_FluxTunableTransmonQCQPair(FluxTunableTransmonPair):
    # gates: Dict[str, TwoQubitGate] = field(default_factory=dict)
 
    def CZ(self):
        self.qubit_control.z.play("cz_square")
        self.coupler.play("cz_square")