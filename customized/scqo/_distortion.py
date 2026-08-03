"""Neutral flux-distortion facts -> QM OPX ``exponential_filter`` config values.

Pure config-value helpers (no push, no quam import): turn the scqo flux-channel
facts ``distortion_amp[]`` (relative amplitudes ``A_i``) + ``distortion_tau_s[]``
(seconds) into the value a QM LF-FEM z port's ``opx_output.exponential_filter``
accepts. The live OPX (QOP >= 3.3) takes the SUM form directly; QOP 3.4.1 takes
the single-pole CASCADE (from scqat), with an overall ``scale`` applied to the
FIR/waveform. Amplitudes are already relative (``amp/a_dc``), so the SUM mapping
is purely ``tau: seconds -> ns``.

These are library helpers a notebook/CLI calls with the recorded facts; wiring
them into an auto-push knob is a separate decision (the ``distortion_*`` facts
stay physical.json record-only today).
"""

from __future__ import annotations

from typing import Any, Sequence

#: OPX LF-FEM sample period (1 GS/s), seconds.
OPX_TS_S = 1e-9


def to_exponential_filter(
    amps: Sequence[float], taus_s: Sequence[float]
) -> list[list[float]]:
    """The QOP >= 3.3 SUM value for ``z.opx_output.exponential_filter``:
    ``[[A_i, tau_i_ns], ...]`` — amplitudes verbatim (already relative), tau s->ns.
    """
    if len(amps) != len(taus_s):
        raise ValueError(
            f"amps ({len(amps)}) and taus_s ({len(taus_s)}) must be equal length")
    return [[float(a), float(t) * 1e9] for a, t in zip(amps, taus_s)]


def to_exponential_filter_cascade(
    amps: Sequence[float], taus_s: Sequence[float], *, ts_s: float = OPX_TS_S
) -> dict[str, Any]:
    """The QOP 3.4.1 single-pole CASCADE value + scale:
    ``{"exponential_filter": [[A_c, tau_c_ns], ...], "scale": float}``.

    Apply ``scale`` to the FIR coefficients or the flux-waveform amplitude per your
    QOP. The facts are relative (a_dc factored out), so ``a_dc=1.0`` is passed to
    the decomposition (which also satisfies its ``a_dc > MIN_A_DC`` guard).
    """
    from scqat.tools.flux_predistortion import exp_sum_to_cascade

    casc = exp_sum_to_cascade(amps, taus_s, a_dc=1.0, ts_s=ts_s)
    return {
        "exponential_filter": [
            [a, t * 1e9] for a, t in zip(casc["amps_c"], casc["taus_c_s"])
        ],
        "scale": casc["scale"],
    }
