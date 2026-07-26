"""The QM side of the neutral ``reset_method``: pass thermal through, refuse the rest.

scqo widened ``reset_method`` to ``Literal["thermal", "active"]`` when active
reset landed on the Qblox backend. That widening is repo-wide — the field is on
the shared ``QubitResetParameters`` mixin, so ``reset_method="active"`` now
passes validation on EVERY backend, including this one. Without this helper the
12 QM shells (which hand a literal ``reset_type="thermal"`` to the probes) would
accept the flag and thermalize anyway: the run completes, the data looks right,
and only the wall clock disagrees. That silent downgrade is exactly what the
capability's BOUNDARY RULE forbids, so every shell resolves its ``reset_type``
here instead of spelling the literal.

WHY NOT JUST IMPLEMENT IT. Nothing technical is missing: QUAM's
``BaseTransmon.reset_qubit_active`` is a full repeat-until-success loop
(measure -> ``assign(state, I > pulse.threshold)`` -> conditional pi, looping
``while_(I > pulse.rus_exit_threshold)`` up to ``max_attempts``), the probes
already forward ``reset_type`` verbatim to ``qubit.reset(...)``, and scqo already
CALIBRATES both thresholds it needs — ``single_shot_readout.update()`` proposes
``readout_threshold`` and ``readout_rus_threshold``, the latter realized here and
nowhere else. Wiring it is roughly a one-token change per shell.

What is missing is EVIDENCE. Active reset is a feedback loop; whether the trigger
path works is not something an offline test can establish, and this driver has
been bitten before by a readout-frame convention that compiled clean and was
wrong on the instrument. So it ships when someone has QM hardware time to verify
it, not before. When that happens: give each shell an allow-list the way
``LCHQBDriver/lchqb/experiments/_reset.py`` does — active reset is invalid
wherever the readout condition is swept (``readout_frequency``,
``readout_power``) or where the experiment IS the discriminator's calibration
(``single_shot_readout``) — and note that scqo's ``active_reset_rounds`` maps
onto ``max_attempts``, which QM treats as an UPPER BOUND (it exits early) where
Qblox plays exactly that many rounds.
"""

from __future__ import annotations

from typing import Any

#: The only method these shells realize. Kept as a name so the refusal message
#: and the returned value cannot drift apart.
THERMAL = "thermal"


def reset_type(experiment: Any) -> str:
    """The QM ``reset_type`` for this run, or a refusal naming the experiment.

    ``reset_method`` crosses the probe boundary verbatim (the neutral vocabulary
    was chosen to match QUAM's own ``reset_type``), so this is a pass-through
    with a guard — not a translation.
    """
    method = getattr(experiment.params, "reset_method", THERMAL)
    if method == THERMAL:
        return THERMAL
    name = getattr(type(experiment), "name", type(experiment).__name__)
    raise ValueError(
        f"{name}: reset_method={method!r} is not realized on the Quantum "
        f"Machines backend — refusing rather than silently resetting thermally. "
        f"Active reset currently runs on the Qblox backend only. QUAM can do it "
        f"(BaseTransmon.reset_qubit_active) and this device already calibrates "
        f"the thresholds it needs, but it is not wired here until it has been "
        f"verified on QM hardware; see customized/scqo/experiments/_reset.py. "
        f"Use reset_method='thermal'."
    )
