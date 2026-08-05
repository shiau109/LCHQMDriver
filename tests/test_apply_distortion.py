"""Unit tests for apply_distortion_from_state with an INJECTED fake session — no
scqo config and no QM cluster. The live ``build_session`` -> facts -> apply path is
scqo-owned and exercised by the ``--dry-run`` smoke in the plan's verification.
"""

from types import SimpleNamespace

import pytest

from customized.scqo.apply_distortion import apply_distortion_from_state


def _machine(existing=None):
    """A duck-typed QUAM with a recording ``save``: machine.qubits['q1'].z.opx_output."""
    saves: list = []
    port = SimpleNamespace(exponential_filter=list(existing) if existing else [])
    z = SimpleNamespace(opx_output=port)
    m = SimpleNamespace(qubits={"q1": SimpleNamespace(z=z)}, _saves=saves)
    m.save = lambda **kw: saves.append(kw)
    return m


def _session(machine, facts):
    """A fake scqo Session exposing exactly what the helper reads."""
    roster = SimpleNamespace(default_channel=lambda t, k: f"{t}_{'z' if k == 'flux' else k}")
    backend = SimpleNamespace(machine=machine, roster=roster)
    physical = SimpleNamespace(get=lambda entity, field: facts.get((entity, field)))
    return SimpleNamespace(
        backend=backend, physical=physical, cooldown_id="cd1", setup_name="s1"
    )


def _facts(amps, taus):
    return {("q1_z", "distortion_amp"): amps, ("q1_z", "distortion_tau_s"): taus}


def test_reads_flux_channel_applies_and_saves():
    m = _machine()
    sess = _session(m, _facts([0.05, -0.03], [100e-9, 3000e-9]))
    out = apply_distortion_from_state("q1", session=sess)  # cfg=None -> bare save()
    assert out["channel"] == "q1_z"  # fact-vs-mode bridge: q1 -> q1_z
    assert m.qubits["q1"].z.opx_output.exponential_filter == [
        [0.05, 100.0], [-0.03, 3000.0]]  # tau s->ns
    assert out["saved"] is True and len(m._saves) == 1  # machine.save() once
    assert out["scale"] == 1.0 and out["existing_taps"] == 0


def test_dry_run_writes_nothing():
    m = _machine()
    out = apply_distortion_from_state(
        "q1", session=_session(m, _facts([0.05], [100e-9])), dry_run=True)
    assert out["saved"] is False and m._saves == []


def test_save_false_writes_nothing():
    m = _machine()
    apply_distortion_from_state(
        "q1", session=_session(m, _facts([0.05], [100e-9])), save=False)
    assert m._saves == []


def test_extend_appends_to_existing_without_warning():
    m = _machine(existing=[[0.9, 999.0]])
    apply_distortion_from_state(
        "q1", session=_session(m, _facts([0.02], [50e-9])), replace=False)
    assert m.qubits["q1"].z.opx_output.exponential_filter == [
        [0.9, 999.0], [0.02, 50.0]]  # old kept, new appended


def test_replace_over_nonempty_filter_warns():
    m = _machine(existing=[[0.9, 999.0]])
    with pytest.warns(UserWarning, match="replacing 1 existing"):
        apply_distortion_from_state("q1", session=_session(m, _facts([0.05], [100e-9])))


def test_missing_both_facts_raises_and_saves_nothing():
    m = _machine()
    with pytest.raises(SystemExit, match="no accepted distortion facts"):
        apply_distortion_from_state("q1", session=_session(m, _facts(None, None)))
    assert m._saves == []


def test_only_one_paired_fact_present_still_raises():
    m = _machine()
    sess = _session(m, {("q1_z", "distortion_amp"): [0.05]})  # taus missing -> None
    with pytest.raises(SystemExit, match="no accepted distortion facts"):
        apply_distortion_from_state("q1", session=sess)


def test_cascade_warns_about_manual_scale():
    m = _machine()
    sess = _session(m, _facts([0.05, 0.02], [100e-9, 12e-9]))
    with pytest.warns(UserWarning, match="cascade"):
        out = apply_distortion_from_state("q1", session=sess, form="cascade")
    assert out["scale"] > 0  # a real cascade scale rode through
