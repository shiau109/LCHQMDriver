"""``qubit_spectroscopy_cryoscope.validate_inputs`` — the long-time cryoscope probe's gate.

The probe builds a single-qubit spectroscopy sequence that parks an idle-relative
flux pulse and drives at each wait-time into it. The pre-flight checks are pure
over stub qubits (no QOP, no config): more than one target, a missing flux line,
and a parked flux whose ``idle + excursion`` clips the port or needs an
``amplitude_scale`` QUA cannot express. A legal call returns the ``const``
reference amplitude the volts->scale conversion divides by.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from customized.probes.qubit_spectroscopy_cryoscope import validate_inputs


class _Qubits(list):
    """Minimal stand-in for the probe's BatchableList (len / index / names)."""

    def get_names(self):
        return [q.name for q in self]


def _z(const_amp: float = 0.2, *, output_mode: str = "direct",
       joint_offset: float = 0.0) -> SimpleNamespace:
    return SimpleNamespace(
        name="q0_z",
        opx_output=SimpleNamespace(output_mode=output_mode),
        operations={"const": SimpleNamespace(amplitude=const_amp)},
        joint_offset=joint_offset,
    )


def _qubit(name: str = "q0", **z_kwargs) -> SimpleNamespace:
    return SimpleNamespace(name=name, z=_z(**z_kwargs))


def test_legal_call_returns_the_const_reference():
    amp_ref = validate_inputs(_Qubits([_qubit()]), flux_amp_v=0.1, flux_point="joint")
    assert amp_ref == pytest.approx(0.2)  # the stored const amplitude


def test_more_than_one_target_refused_by_name():
    with pytest.raises(ValueError, match="one target at a time"):
        validate_inputs(_Qubits([_qubit("q0"), _qubit("q1")]), flux_amp_v=0.1, flux_point="joint")


def test_missing_flux_line_refused():
    with pytest.raises(ValueError, match="no flux line"):
        validate_inputs(_Qubits([SimpleNamespace(name="q0", z=None)]), flux_amp_v=0.1, flux_point="joint")


def test_idle_plus_excursion_over_rail_refused():
    # direct-mode rail is 0.5 V; 0.4 V idle + 0.2 V excursion = 0.6 V clips.
    with pytest.raises(ValueError, match="full scale"):
        validate_inputs(_Qubits([_qubit(joint_offset=0.4)]), flux_amp_v=0.2, flux_point="joint")


def test_amplitude_scale_out_of_range_refused():
    # const 0.2 V, excursion 0.5 V -> scale 2.5 >= QUA's +/-2 range (rail fine at 0.5).
    with pytest.raises(ValueError, match="amplitude_scale"):
        validate_inputs(_Qubits([_qubit(const_amp=0.2)]), flux_amp_v=0.5, flux_point="joint")
