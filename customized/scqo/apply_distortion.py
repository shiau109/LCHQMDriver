"""One command: accepted cryoscope distortion facts -> the QM z-output filter.

After ``scqo run qubit_spectroscopy_cryoscope --target q1`` (or the ramsey one) +
``scqo accept``, the fit's ``distortion_amp``/``distortion_tau_s`` live as FACTS in
scqo's ``physical.json`` — record-only, never auto-pushed. This turns them into the
OPX predistortion filter in one step: resolve the ACTIVE scqo device/setup (the same
selection ``scqo run`` uses), read the accepted taps for ``<target>``'s flux channel,
write them onto ``machine.qubits[<target>].z.opx_output.exponential_filter`` via
:func:`customized.scqo._distortion.apply_exponential_filter`, and save the setup's
``state.json``. Fully OFFLINE — ``build_session`` loads the QUAM from JSON and never
opens a ``QuantumMachinesManager``.

Run it (in ``.venv-qm``)::

    python -m customized.scqo.apply_distortion --target q1
    python -m customized.scqo.apply_distortion --target q1 --dry-run   # preview only
    python -m customized.scqo.apply_distortion --target q1 --extend    # append a residual

It never runs automatically on ``scqo accept`` — applying predistortion is a
deliberate, opt-in step (measure a fresh full correction on a filter-CLEARED line;
``--extend`` refines a residual measured with the current filter active).
"""

from __future__ import annotations

import argparse
import warnings
from typing import Any

from customized.scqo._distortion import apply_exponential_filter

#: the roster channel kind of a qubit's flux line (catalog CHANNELS).
FLUX_KIND = "flux"


def apply_distortion_from_state(
    target: str,
    *,
    replace: bool = True,
    form: str = "sum",
    config_path: str | None = None,
    session: Any = None,
    cfg: Any = None,
    save: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply the accepted distortion facts for ``target`` to the QM z filter.

    Resolves the ACTIVE scqo selection (unless ``session`` is injected — for tests),
    reads ``distortion_amp``/``distortion_tau_s`` for the target's flux channel from
    the physical store, writes them to the QUAM z-output ``exponential_filter``, and
    (unless ``dry_run`` or ``save=False``) saves the setup's ``state.json``. OFFLINE.

    Returns a summary dict: ``target``, ``channel``, ``amps``, ``taus_s``,
    ``existing_taps``, ``state_dir``, ``saved``, plus ``apply_exponential_filter``'s
    ``exponential_filter`` + ``scale``. Raises ``SystemExit`` when the target has no
    accepted distortion facts yet.
    """
    if session is None:
        from scqo.cli import build_session  # lazy: keep module import scqo-free

        session, cfg = build_session(config_path)

    channel = session.backend.roster.default_channel(target, FLUX_KIND)  # q1 -> q1_z
    amps = session.physical.get(channel, "distortion_amp")
    taus_s = session.physical.get(channel, "distortion_tau_s")
    if amps is None or taus_s is None:
        raise SystemExit(
            f"no accepted distortion facts for {channel} — run and accept a "
            f"cryoscope for {target!r} first (distortion_amp/distortion_tau_s are "
            f"unset in physical.json)"
        )

    machine = session.backend.machine
    try:
        existing = len(list(machine.qubits[target].z.opx_output.exponential_filter or []))
    except (KeyError, TypeError, AttributeError):
        existing = 0  # apply_exponential_filter raises the friendly target/z error

    if replace and existing:
        warnings.warn(
            f"replacing {existing} existing exponential_filter tap(s) on {channel}; "
            f"a full correction must be MEASURED on a filter-cleared line (use "
            f"--extend to refine a residual instead)",
            stacklevel=2,
        )
    if form == "cascade":
        warnings.warn(
            "form='cascade' (QOP 3.4.1): apply the returned 'scale' to the flux "
            "waveform amplitude yourself — this command does not automate it",
            stacklevel=2,
        )

    result = apply_exponential_filter(
        machine, target, amps, taus_s, replace=replace, form=form
    )

    state_dir = None
    if cfg is not None:
        from scqo.datastore import setup_backend_config_dir

        state_dir = str(
            setup_backend_config_dir(
                cfg.data_root, cfg.device, session.cooldown_id, session.setup_name
            )
        )
    did_save = bool(save and not dry_run)
    if did_save:
        if state_dir:
            machine.save(path=state_dir)
        else:
            machine.save()

    return {
        "target": target,
        "channel": channel,
        "amps": list(amps),
        "taus_s": list(taus_s),
        "existing_taps": existing,
        "state_dir": state_dir,
        "saved": did_save,
        **result,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog="python -m customized.scqo.apply_distortion",
        description="Apply accepted cryoscope distortion taps to the QM z-output "
        "exponential_filter for the ACTIVE scqo device/setup.",
    )
    p.add_argument("--target", required=True, help="qubit/mode name, e.g. q1")
    p.add_argument(
        "--extend",
        action="store_true",
        help="append to the existing filter (refine a residual) instead of "
        "overwriting it",
    )
    p.add_argument(
        "--form",
        choices=("sum", "cascade"),
        default="sum",
        help="sum (QOP >= 3.3, default) or cascade (QOP 3.4.1)",
    )
    p.add_argument(
        "--config", default=None, help="scqo config.toml path (default: active selection)"
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="resolve + preview what would be written; save nothing",
    )
    args = p.parse_args(argv)

    out = apply_distortion_from_state(
        args.target,
        replace=not args.extend,
        form=args.form,
        config_path=args.config,
        dry_run=args.dry_run,
    )

    verb = "would write" if args.dry_run else ("appended" if args.extend else "wrote")
    print(
        f"{args.target} ({out['channel']}): {verb} "
        f"{len(out['exponential_filter'])} exponential_filter tap(s)"
    )
    for pair in out["exponential_filter"]:
        a, tau_ns = list(pair)
        print(f"    A={a:+.5g}  tau={tau_ns:.4g} ns")
    if out["scale"] != 1.0:
        print(f"    scale={out['scale']:.6g}  (apply to the flux waveform amplitude)")
    if out["state_dir"]:
        label = "target" if args.dry_run else "saved to"
        print(f"  {label}: {out['state_dir']}")
    if args.dry_run:
        print("  --dry-run: nothing written")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
