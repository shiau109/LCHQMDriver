"""The QM parity-monitor shell's pure decisions (no QUA, no instrument).

Everything here is arithmetic the shell owns and the probe trusts:

* ns -> QUA clock cycles for the fixed idle (4 ns clock, 16 ns floor);
* the depletion wait's precedence AND the fact that 0 survives the floor —
  "measured, needs no settle" is a real answer, and rounding it up to 16 ns
  would silently lengthen every shot;
* the shot period, which is the telegraph timebase: the neutral layer divides
  a per-shot switching probability by it, so a period that disagrees with what
  the program plays scales every reported rate linearly.

The absence of a qubit reset is a property of the QUA probe module, checked by
reading it — a QUA program cannot be built without an instrument-grade config,
and a probe that silently regained a `qubit.reset()` would be undetectable in
the data.
"""

from __future__ import annotations

import ast
from pathlib import Path
from types import SimpleNamespace

import pytest

from customized.scqo.experiments.qubit_parity_switch import _cycles

PROBE = Path(__file__).resolve().parents[1] / "customized" / "probes" / "qubit_parity_switch.py"


def _called_names() -> set[str]:
    """Every callee spelling in the probe, as source text.

    An AST walk, not a substring scan: the module docstring DESCRIBES the calls
    that must not appear (``readout_state``, ``.average()``, ``qubit.reset``)
    and explains why, so a text search over the file finds its own
    documentation and reports the opposite of the truth.
    """
    tree = ast.parse(PROBE.read_text(encoding="utf-8"))
    return {ast.unparse(node.func) for node in ast.walk(tree)
            if isinstance(node, ast.Call)}


class TestCycleConversion:

    def test_snaps_to_the_4ns_clock(self):
        assert _cycles(2000) == 500
        assert _cycles(2002) == 500     # 2002 -> 500.5 -> 500 cycles = 2000 ns
        assert _cycles(2006) == 502     # rounds up

    def test_floors_at_the_16ns_minimum_wait(self):
        assert _cycles(4) == 4          # 1 cycle requested, 4 is the floor
        assert _cycles(16) == 4
        assert _cycles(0) == 4


class TestShotPeriod:

    @staticmethod
    def _machine(*, y90=40, x90=40, readout=2000):
        qubit = SimpleNamespace(
            xy=SimpleNamespace(operations={
                "y90": SimpleNamespace(length=y90),
                "x90": SimpleNamespace(length=x90)}),
            resonator=SimpleNamespace(operations={
                "readout": SimpleNamespace(length=readout)}),
        )
        return SimpleNamespace(qubits={"q1": qubit})

    def test_sums_the_scheduled_durations(self):
        from customized.scqo.experiments.qubit_parity_switch import QMQubitParitySwitch

        # 500 cycles idle (2000 ns) + 250 cycles depletion (1000 ns)
        # + 40 + 40 ns pi/2 + 2000 ns readout = 5080 ns
        period = QMQubitParitySwitch._shot_period_s(
            self._machine(), "q1", idle_cycles=500, depletion_cycles=250)
        assert period == pytest.approx(5080e-9)

    def test_zero_depletion_shortens_the_period(self):
        from customized.scqo.experiments.qubit_parity_switch import QMQubitParitySwitch

        with_wait = QMQubitParitySwitch._shot_period_s(
            self._machine(), "q1", idle_cycles=500, depletion_cycles=250)
        without = QMQubitParitySwitch._shot_period_s(
            self._machine(), "q1", idle_cycles=500, depletion_cycles=0)
        assert with_wait - without == pytest.approx(1000e-9)


class TestProbeHasNoQubitReset:
    """The defining absence. Between shots only the RESONATOR is waited out."""

    def test_probe_never_calls_qubit_reset(self):
        calls = _called_names()
        assert not [c for c in calls if c.endswith(".reset")], calls
        # and takes no reset argument at all — there is nothing to pass
        tree = ast.parse(PROBE.read_text(encoding="utf-8"))
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        names |= {a.arg for n in ast.walk(tree)
                  if isinstance(n, ast.FunctionDef)
                  for a in [*n.args.args, *n.args.kwonlyargs]}
        assert "reset_type" not in names

    def test_probe_waits_the_resonator_between_shots(self):
        assert "qubit.resonator.wait" in _called_names()

    def test_probe_never_averages_the_shots(self):
        """Every shot is a sample of the telegraph; averaging them destroys the
        signal. The legacy exclude/ node carried a `.average()` that was a
        no-op only because one buffer was ever produced."""
        calls = _called_names()
        assert not [c for c in calls if c.endswith(".average")], calls
        assert any(c.endswith(".buffer") for c in calls), calls

    def test_probe_does_not_use_readout_state(self):
        """`readout_state()` ends with its OWN depletion wait, which would make
        two per shot in discriminated mode and desynchronize the timebase from
        the shot period the shell reports (see the probe's docstring)."""
        calls = _called_names()
        assert not [c for c in calls if c.endswith("readout_state")], calls
        # ... and does the measurement itself instead
        assert "qubit.resonator.measure" in calls

    def test_probe_plays_y90_then_x90(self):
        """Order matters: the SECOND pulse is the 90-degree-shifted one, so the
        measured quantity is sin (odd in parity) rather than cos (even)."""
        tree = ast.parse(PROBE.read_text(encoding="utf-8"))
        played = [node.args[0].value for node in ast.walk(tree)
                  if isinstance(node, ast.Call)
                  and ast.unparse(node.func).endswith("xy.play")
                  and node.args and isinstance(node.args[0], ast.Constant)]
        assert played == ["y90", "x90"], played
