"""Joint two-qubit populations -> the role-named marginals scqo's pair swap
maps contract for.

Both swap probes (``pair_qq_chevron``, ``pair_qcq_fixed_time``) read BOTH
members out 2-level and save the four joint populations P00/P01/P10/P11 as
``state_gg/state_ge/state_eg/state_ee``, with the FIRST digit the vendor's
control qubit. scqo's contract is role-named (``p_high``/``p_low``/``p_ee``),
so the mapping needs the control/target -> high/low orientation the adapter
resolved once in ``probe()``.

This is data SHAPING, deliberately not in ``_vendor.py`` (which is name
resolution). It lives in a mixin because both adapters need it byte-identically
and a swap map's reduction is not something either should own alone.
"""

from __future__ import annotations

import xarray as xr


class JointPopulationMixin:
    """``reduce_raw`` for the pair swap maps. Requires ``self._high_side``."""

    #: "control" | "target" — which vendor side the roster's `high` role is.
    #: Set once in probe(), via _vendor.role_side(self, "high", ...).
    _high_side: str

    def reduce_raw(self, raw: xr.Dataset) -> xr.Dataset:
        """Joint populations -> the two role-named marginals + the |ee> witness.

        ``p_high``/``p_low`` are the members' excited-state probabilities
        (marginals of the joint distribution, so an excitation that LEFT one
        qubit is seen ARRIVING at the other — a single folded signal could not
        tell that from decay). ``p_ee`` is the double-excitation witness: it is
        what separates a genuine single-excitation swap from heating, imperfect
        reset, or a |11>-|02> leak. ``p_gg`` rides along as an extra (contracts
        allow extras) — it is exactly ``1 - p_high - p_low + p_ee``.
        """
        if "state_ee" not in raw.data_vars:
            raise ValueError(
                f"{type(self).name}: the probe returned no joint populations "
                f"(data_vars={list(raw.data_vars)}). The swap maps contract for "
                f"populations, so they need state discrimination — run "
                f"single_shot_readout and accept its readout_rotation_rad / "
                f"readout_threshold suggestions first.")
        ee = raw["state_ee"]
        p_control = raw["state_eg"] + ee   # control excited, either target state
        p_target = raw["state_ge"] + ee    # target excited, either control state
        high_is_control = self._high_side == "control"
        return xr.Dataset({
            "p_high": p_control if high_is_control else p_target,
            "p_low": p_target if high_is_control else p_control,
            "p_ee": ee,
            "p_gg": raw["state_gg"],
        })
