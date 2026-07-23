"""QM readout-discriminator calibration — the vendor-knob math (pure numpy).

Mirrors the vendored qualibrate ``07_iq_blobs`` analysis
(``calibration_utils/iq_blobs/analysis.py``) so a scqo ``single_shot_readout`` run can
recalibrate the QM readout discriminator without the GUI. Kept dependency-free (no
qualibrate/quam import) so it is unit-testable and stable against ``sync_official.py``.

UNITS: everything here is in the ACQUISITION frame's native units — raw demod on the
scqo path (the probe does NOT convert to Volts). The returned ``ge_threshold`` /
``rus_exit_threshold`` are therefore ALREADY in the units ``operation.threshold``
stores; the caller writes them as-is. Do NOT apply 07's ``* length / 2**12`` — that
factor inverts a Volt conversion that never happened on this path (double-division).

ANGLE: a single final angle (with 07's ``+pi`` fix so the rotated excited blob sits
above ground) drives BOTH the returned rotation and the threshold frame. The caller
ACCUMULATES it: ``integration_weights_angle -= delta_angle_rad`` (07's semantics; 07's
stored ``iw_angle`` is the post-fix angle — xarray ``assign`` aliases the mutated
DataArray, verified).
"""

from __future__ import annotations

import numpy as np
from scipy.optimize import minimize


def _false_detections(threshold: float, ig_rot: np.ndarray, ie_rot: np.ndarray) -> float:
    """Total misclassification count at a rotated-I threshold (mirrors 07's helper,
    calibration_utils/iq_blobs/analysis.py:143-148)."""
    if np.mean(ig_rot) < np.mean(ie_rot):
        return float(np.sum(ig_rot > threshold) + np.sum(ie_rot < threshold))
    return float(np.sum(ig_rot < threshold) + np.sum(ie_rot > threshold))


def compute_qm_discriminator(mean_g, mean_e, shots_g, shots_e) -> dict:
    """QM discriminator knobs from the g/e blob centers and the per-shot |g>/|e> clouds.

    Parameters
    ----------
    mean_g, mean_e : (I, Q)
        The ground / excited blob centers (scqat GMM means), acquisition-frame units.
    shots_g, shots_e : (I_array, Q_array)
        Per-shot clouds for the |g> / |e> preparations (same units).

    Returns
    -------
    dict with (all acquisition-frame / raw-demod units):
        delta_angle_rad : the rotation putting the g->e axis on +I with Ie > Ig; the
            caller does ``integration_weights_angle -= delta_angle_rad``.
        ge_threshold : rotated-I decision threshold (false-detection minimum).
        rus_exit_threshold : rotated-I ground-blob mode (active-reset exit).
    """
    ig_c, qg_c = float(mean_g[0]), float(mean_g[1])
    ie_c, qe_c = float(mean_e[0]), float(mean_e[1])
    ig = np.asarray(shots_g[0], dtype=float).ravel()
    qg = np.asarray(shots_g[1], dtype=float).ravel()
    ie = np.asarray(shots_e[0], dtype=float).ravel()
    qe = np.asarray(shots_e[1], dtype=float).ravel()

    # 07's angle: put the g->e separation on the I axis (from the blob centers).
    angle = float(np.arctan2(qe_c - qg_c, ig_c - ie_c))
    cos_a, sin_a = np.cos(angle), np.sin(angle)
    # +pi fix so the rotated EXCITED blob sits ABOVE ground (Ie_rot > Ig_rot).
    if (ig_c - ie_c) * cos_a - (qg_c - qe_c) * sin_a > 0:
        angle += np.pi
        cos_a, sin_a = np.cos(angle), np.sin(angle)

    ig_rot = ig * cos_a - qg * sin_a
    ie_rot = ie * cos_a - qe * sin_a

    # RUS exit = the mode (tallest histogram bin) of the rotated ground blob.
    counts, edges = np.histogram(ig_rot, bins=100)
    rus_exit_threshold = float(edges[1:][int(np.argmax(counts))])

    # ge threshold = the rotated-I cut minimizing total misclassification, seeded at
    # the midpoint of the two rotated blob means.
    seed = 0.5 * (float(np.mean(ig_rot)) + float(np.mean(ie_rot)))
    res = minimize(_false_detections, seed, args=(ig_rot, ie_rot), method="Nelder-Mead")
    ge_threshold = float(res.x[0])

    return {
        "delta_angle_rad": float(angle),
        "ge_threshold": ge_threshold,
        "rus_exit_threshold": rus_exit_threshold,
    }
