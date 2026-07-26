"""The QM shells refuse ``reset_method="active"`` instead of thermalizing quietly.

scqo widened the neutral Literal when active reset landed on Qblox. The field
lives on a SHARED mixin, so the flag now validates here too — and these shells
used to hand the probes a hardcoded ``reset_type="thermal"``, which would have
accepted it and reset thermally anyway. That is the one failure this parameter
cannot survive: the run completes, the fit is fine, and the only evidence is a
wall clock nobody reads.

Both tests are deliberately QUAM-free (no ``machine`` fixture, so they run on
every checkout regardless of the ``my_quam.py`` toggle): the policy is a pure
function of Parameters, and the second test is a source-level invariant.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from customized.scqo.experiments._reset import reset_type

SHELLS = Path(__file__).resolve().parents[1] / "customized" / "scqo" / "experiments"


def _shell(name: str, **params):
    """A registered shell instance with no backend — ``reset_type`` reads only
    ``.params`` and the CLASS (for the name), so skipping __init__ keeps this
    test off the vendor stack entirely while still exercising the real class."""
    import customized.scqo.experiments  # noqa: F401  (registers the QM shells)
    from scqo.experiments import get

    cls = get(name)
    exp = cls.__new__(cls)
    exp.params = cls.Parameters(targets=["q1"], **params)
    return exp


def test_thermal_passes_through_unchanged():
    """The neutral vocabulary was chosen to match QUAM's own ``reset_type``, so
    the supported case is a pass-through, not a translation."""
    assert reset_type(_shell("qubit_relaxation")) == "thermal"
    assert reset_type(_shell("qubit_relaxation", reset_method="thermal")) == "thermal"


def test_active_is_refused_and_says_where_it_does_work():
    """Named refusal: the experiment, the backend that has it, and the file to
    read before wiring it here."""
    with pytest.raises(ValueError) as err:
        reset_type(_shell("qubit_relaxation", reset_method="active"))

    message = str(err.value)
    assert "qubit_relaxation" in message
    assert "Qblox" in message
    assert "thermal" in message


def test_no_shell_hardcodes_the_reset_type():
    """The invariant that keeps the guard from being bypassed by the next shell
    someone copies from a neighbour. Every shell resolves through the helper."""
    offenders = []
    for path in sorted(SHELLS.glob("*.py")):
        if path.name.startswith("_"):
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            code = line.split("#", 1)[0]
            if 'reset_type="' in code or "reset_type='" in code:
                offenders.append(f"{path.name}:{lineno}: {line.strip()}")
    assert not offenders, (
        "resolve reset_type through customized/scqo/experiments/_reset.py:\n  "
        + "\n  ".join(offenders))
