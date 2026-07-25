"""Raw-vendor access for the QM probes — the one place that leaves the neutral surface.

Since the greenfield model a probe reads its NEUTRAL state through the channel
entity that owns the knob (``self.device.channel(target, "readout")``), which
serves the SCQO runtime value whether ``self.device`` is the Session's
RecordingDevice or a bare :class:`~customized.scqo.backend.QMDeviceModel`.

The QUAM tree itself is not resolved here — every probe takes the whole
``backend.machine`` plus a ``BatchableList`` of QUAM qubits
(``customized/probes/_lib.select_qubits``), because a QUA program is built out of
the vendor's own pulse macros. What DOES need resolving is the handful of places
where scqo hands a ROSTER name and the probe wants a VENDOR one:

* a foreign flux source (``flux_component``) — scqo names a roster entity (a
  qubit mode, or a tracked coupler mode like ``q1_q2_c``), while the probes'
  ``z_source`` names a QUAM object (``machine.qubits[...]`` or
  ``machine.qubit_pairs[...].coupler``);
* a pair target — scqo names a composite (``q1_q2``), while QM names its pairs
  after the coupler (``coupler_q1_q2``), so the two genuinely differ.

Both joins go through the roster and the backend's own resolution, never through
string arithmetic on the entity name. Entity names are resolved the core
power_chain way: ask the roster for the target's DEFAULT channel of a kind, then
address the vendor tree by that name (``DeviceModel`` has no ``channel()``; only
``RecordingDevice`` does). Going through the channel KIND is also the capability
guard — an entity with no flux channel fails on a clear roster error here instead
of deep inside a QUA program.
"""

from __future__ import annotations

from typing import Any


def _key_of(mapping: Any, obj: Any, *, attr: str | None = None) -> list[str]:
    """The key(s) of a QUAM container whose entry IS ``obj`` (or whose entry's
    ``attr`` is). Identity, never name equality: a QUAM component's ``name`` is
    derived from its ``id`` and need not be the key its parent files it under."""
    return [key for key, value in (mapping or {}).items()
            if (getattr(value, attr, None) if attr else value) is obj]


def vendor_pair(experiment: Any, composite: str) -> Any:
    """The raw QUAM ``qubit_pair`` behind a roster COMPOSITE name.

    Resolved by the backend (by name first, else by the composite's high/low
    membership): QM names its pairs after the coupler — ``coupler_q1_q2`` — so
    a roster composite named ``q1_q2`` is NOT a key of ``machine.qubit_pairs``
    and must never be used as one.
    """
    return experiment.backend.device.component(composite).vendor


def vendor_pair_name(experiment: Any, composite: str) -> str:
    """The KEY of ``machine.qubit_pairs`` for a roster composite — what the
    probe helpers (``_lib.select_qubit_pairs``) select pairs by."""
    pairs = getattr(experiment.backend.machine, "qubit_pairs", {}) or {}
    hits = _key_of(pairs, vendor_pair(experiment, composite))
    if len(hits) == 1:
        return hits[0]
    raise ValueError(
        f"{composite!r}: the QUAM qubit_pair it resolves to is not a unique "
        f"entry of machine.qubit_pairs (matches {sorted(hits)}; pairs: "
        f"{sorted(pairs)})")


def flux_source_name(experiment: Any, entity: str, *,
                     qubit_only: bool = False) -> str:
    """The VENDOR name a foreign flux source is addressed by in the probes.

    ``entity`` is the roster name the operator typed (``scqo run ... --set
    flux_component=q1_q2_c``); the returned string is what the probe's
    ``z_source`` / ``z_source_qubit`` argument takes — a key of
    ``machine.qubits`` for a qubit's own z line, or a key of
    ``machine.qubit_pairs`` for a coupler (the probe reaches the coupler as
    ``machine.qubit_pairs[<name>].coupler``).

    ``qubit_only=True`` for probes that play a z PULSE through
    ``machine.qubits[...].z`` and therefore cannot drive a coupler at all
    (``customized/probes/qubit_spectroscopy_flux.py``): a coupler entity is
    refused here, with the reason, rather than raising a bare KeyError inside
    the probe.
    """
    machine = experiment.backend.machine
    view = experiment.backend.device.component(
        experiment.device.roster.default_channel(entity, "flux"))
    qubit = getattr(view, "qubit", None)
    if qubit is not None:  # an ordinary qubit's own z line
        hits = _key_of(getattr(machine, "qubits", {}), qubit)
        if len(hits) == 1:
            return hits[0]
        raise ValueError(
            f"flux_component={entity!r}: its QUAM qubit is not a unique entry "
            f"of machine.qubits (matches {sorted(hits)})")
    if qubit_only:
        raise ValueError(
            f"flux_component={entity!r} is a coupler: this probe plays its "
            f"flux as a z PULSE on a QUAM qubit, and a tunable coupler has no "
            f"qubit to play it on — sweep a qubit's z line, or use "
            f"resonator_spectroscopy_flux (whose probe drives the coupler "
            f"element directly)")
    # A coupler: the probe reaches it through its PAIR. Match the vendor object
    # the backend resolved, never the name (QM names its pairs after the
    # coupler, e.g. `coupler_q1_q2`, which the roster need not repeat).
    pairs = getattr(machine, "qubit_pairs", {}) or {}
    hits = _key_of(pairs, view.vendor, attr="coupler")
    if len(hits) == 1:
        return hits[0]
    raise ValueError(
        f"flux_component={entity!r} resolves to a coupler the probe cannot "
        f"address: " + (f"several QUAM pairs carry it ({sorted(hits)})"
                        if hits else
                        f"no QUAM qubit_pair in this state owns it "
                        f"(pairs: {sorted(pairs)})"))
