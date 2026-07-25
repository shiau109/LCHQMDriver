"""The probes' door out of the neutral surface (``customized/scqo/experiments/_vendor.py``).

QM probes take the raw QUAM tree and address it by VENDOR name, while scqo hands
the experiment ROSTER names — a foreign flux source (``flux_component``) and a
pair target are the two places where the two namespaces meet. These tests pin
that join against the stub QUAM tree from ``conftest.py``, whose names disagree
on purpose (roster ``q1_q2`` / ``q1_q2_c`` vs QUAM ``coupler_q1_q2``), so a
resolution that fell back to string arithmetic would fail here.

No QUA program is built (that needs an instrument-grade config); what is under
test is exactly the name resolution the probe call sites do first.
"""

from __future__ import annotations

import pytest

from conftest import make_experiment


def _flux_experiment(backend, roster, **kw):
    from customized.scqo.experiments.resonator_spectroscopy_flux import (
        QMResonatorSpectroscopyFlux,
    )

    params = QMResonatorSpectroscopyFlux.Parameters(targets=["q1"], **kw)
    return make_experiment(QMResonatorSpectroscopyFlux, backend, roster, params)


def test_flux_source_resolves_a_qubits_own_z_line(backend, roster):
    from customized.scqo.experiments._vendor import flux_source_name

    exp = _flux_experiment(backend, roster, flux_component="q2")
    assert flux_source_name(exp, "q2") == "q2"  # a key of machine.qubits


def test_flux_source_resolves_a_coupler_to_its_quam_pair(backend, roster):
    """The roster names the coupler MODE ``q1_q2_c``; the probe reaches it as
    ``machine.qubit_pairs['coupler_q1_q2'].coupler``. The join is the vendor
    OBJECT the backend resolved, never the name."""
    from customized.scqo.experiments._vendor import flux_source_name

    exp = _flux_experiment(backend, roster, flux_component="q1_q2_c")
    assert flux_source_name(exp, "q1_q2_c") == "coupler_q1_q2"


def test_flux_source_refuses_a_coupler_for_a_z_pulse_probe(backend, roster):
    """qubit_spectroscopy_flux plays the flux as a z PULSE on a QUAM qubit, and a
    tunable coupler has none — refused here with the reason, not deep inside the
    QUA build."""
    from customized.scqo.experiments._vendor import flux_source_name

    exp = _flux_experiment(backend, roster, flux_component="q1_q2_c")
    with pytest.raises(ValueError, match="coupler"):
        flux_source_name(exp, "q1_q2_c", qubit_only=True)


def test_flux_source_refuses_an_entity_with_no_flux_channel(backend, roster):
    """Going through the channel KIND is the capability guard: q3 is a fixed
    transmon with no flux rider, so the roster refuses before any vendor hop."""
    from scqo.roster import RosterError

    from customized.scqo.experiments._vendor import flux_source_name

    exp = _flux_experiment(backend, roster)
    with pytest.raises((RosterError, KeyError), match="flux"):
        flux_source_name(exp, "q3")


def test_pair_target_resolves_to_the_quam_pair_key(backend, roster):
    """``targets`` are ROSTER composite names; ``_lib.select_qubit_pairs``
    selects by QUAM key. QM names its pairs after the coupler, so the two
    genuinely differ."""
    from customized.scqo.experiments._vendor import vendor_pair, vendor_pair_name

    exp = _pair_experiment(backend, roster)
    assert vendor_pair_name(exp, "q1_q2") == "coupler_q1_q2"
    assert vendor_pair(exp, "q1_q2") is backend.machine.qubit_pairs["coupler_q1_q2"]


def _pair_experiment(backend, roster, measure="low"):
    from customized.scqo.experiments.pair_zz_coupler import QMPairZZCoupler

    params = QMPairZZCoupler.Parameters(targets=["q1_q2"], measure=measure)
    return make_experiment(QMPairZZCoupler, backend, roster, params)


@pytest.mark.parametrize("measure,side", [("low", "control"), ("high", "target")])
def test_pair_measure_role_maps_onto_the_vendor_side(backend, roster, measure, side):
    """The neutral high/low ROLE is roster topology; control/target is vendor gate
    plumbing. The stub pair is control=q1 / target=q2 while the roster says
    high=q2 / low=q1, so a positional guess would invert this."""
    exp = _pair_experiment(backend, roster, measure=measure)
    assert exp._measure_side(backend.machine) == side


def test_single_shot_readout_addresses_the_readout_channel(backend, roster):
    """The discriminator proposal writes through the READOUT CHANNEL entity — the
    qubit MODE name carries no knobs since the greenfield split."""
    from customized.scqo.experiments.single_shot_readout import QMSingleShotReadout

    exp = make_experiment(QMSingleShotReadout, backend, roster,
                          QMSingleShotReadout.Parameters(targets=["q1"]))
    view = exp.device.channel("q1", "readout")
    view.readout_rotation_rad = 1.25
    view.readout_threshold = -3e-4
    view.readout_rus_threshold = -1e-4

    pulse = backend.machine.qubits["q1"].resonator.operations["readout"]
    assert pulse.integration_weights_angle == pytest.approx(1.25)
    assert pulse.threshold == pytest.approx(-3e-4)
    assert pulse.rus_exit_threshold == pytest.approx(-1e-4)
    with pytest.raises(KeyError):
        exp.device.component("q1")  # the mode itself carries no knobs
