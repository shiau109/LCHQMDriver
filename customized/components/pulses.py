from quam.core import QuamComponent, quam_dataclass
from quam.components.pulses import Pulse

import numpy as np

@quam_dataclass
class RampPulse(Pulse):
    """Gaussian pulse with flat top QUAM component.

    Args:
        length (int): The total length of the pulse in samples.
        amplitude (float): The amplitude of the pulse in volts.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).

    """

    axis_angle: float = None
    start_value: float = 0
    end_value: float = 0

    def waveform_function(self):

        waveform = np.linspace(self.start_value, self.end_value, self.length)


        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform


@quam_dataclass
class ParaCosinePulse(Pulse):
    """Cosine pulse QUAM component.

    Args:
        length (int): The total length of the pulse in samples.
        amplitude (float): The amplitude of the pulse in volts.
        frequency (float): The frequency of the cosine wave in units of cycles per sample.
        phase (float): The phase offset of the cosine wave in radians.

    """

    amplitude: float = 0.1
    frequency: float = 0.1
    phase: float = 0.0

    def waveform_function(self):
        # Generate time array
        t = np.linspace( 0, self.length ,self.length, endpoint=False)  # An array of size pulse length in ns
        
        # Generate cosine waveform
        waveform = self.amplitude * np.cos(2 * np.pi * self.frequency * t + self.phase)

        return waveform


@quam_dataclass
class CascadeFlatTopGaussianPulse(Pulse):
    """Gaussian pulse with flat top QUAM component.

    Args:
        length (int): The total length of the pulse in samples.
        amplitude (float): The amplitude of the pulse in volts.
        axis_angle (float, optional): IQ axis angle of the output pulse in radians.
            If None (default), the pulse is meant for a single channel or the I port
                of an IQ channel
            If not None, the pulse is meant for an IQ channel (0 is X, pi/2 is Y).
        flat_length (int): The length of the pulse's flat top in samples.
            The rise and fall lengths are calculated from the total length and the
            flat length.
    """

    amplitude: float
    axis_angle: float = None
    flat_length: int
    def waveform_function(self):
        from qualang_tools.config.waveform_tools import flattop_gaussian_waveform

        rise_fall_length = (self.length - self.flat_length) // 2
        if not self.flat_length + 2 * rise_fall_length == self.length:
            raise ValueError(
                "FlatTopGaussianPulse rise_fall_length (=length-flat_length) must be"
                f" a multiple of 2 ({self.length} - {self.flat_length} ="
                f" {self.length - self.flat_length})"
            )

        waveform = flattop_gaussian_waveform(
            amplitude=self.amplitude,
            flat_length=self.flat_length,
            rise_fall_length=rise_fall_length,
            return_part="all",
        )
        waveform = np.array(waveform)

        if self.axis_angle is not None:
            waveform = waveform * np.exp(1j * self.axis_angle)

        return waveform



if __name__ == "__main__":
    # Example usage
    pulse = RampPulse(length=10, start_value=0, end_value=0.5)
    print(pulse.waveform_function())
    print(pulse.__class__.__name__)
    
    # Example usage for CosinePulse
    cosine_pulse = ParaCosinePulse(length=20, amplitude=0.5, frequency=0.1, phase=0.0)
    print(cosine_pulse.waveform_function())
    print(cosine_pulse.__class__.__name__)