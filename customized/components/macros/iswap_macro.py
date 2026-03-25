from quam.core import quam_dataclass
from quam.components.pulses import Pulse
# from quam.components.macro import QubitPairMacro
from customized.components.macros.two_qubit_pair_macro import QubitPairMacro

@quam_dataclass
class ISwapImplementation(QubitPairMacro):
    """ISWAP Operation for a qubit pair"""

    # flux_pulse: Pulse
    flux_pulse: str

    phase_shift_control: float = 0.0
    phase_shift_target: float = 0.0

    def apply(self, *, ctrl_amp=None, cplr_amp=None):

        ctrl_amp_ref = self.qubit_control.z.operations[self.flux_pulse].amplitude
        cplr_amp_ref = self.coupler.operations[self.flux_pulse].amplitude


        self.qubit_control.z.play(self.flux_pulse,amplitude_scale=ctrl_amp/ctrl_amp_ref)
        self.coupler.play(self.flux_pulse,amplitude_scale=cplr_amp/cplr_amp_ref)

        # wait(operation_gap_ns//4)
        
        self.qubit_pair.align()

        # Copy from quam
        # self.flux_pulse.play(amplitude_scale=amplitude_scale)
        # self.qubit_control.align(self.qubit_target)
        # self.qubit_control.xy.frame_rotation(self.phase_shift_control)
        # self.qubit_target.xy.frame_rotation(self.phase_shift_target)
        # self.qubit_pair.align()
