"""The QM flux-distortion config-value wrapper (facts -> exponential_filter).

Pure unit tests: the SUM mapping is amplitudes-verbatim + tau s->ns; the CASCADE
path threads scqat's decomposition. No QOP / instrument needed.
"""

import numpy as np
import pytest

from customized.scqo._distortion import (
    to_exponential_filter,
    to_exponential_filter_cascade,
)


def test_sum_form_maps_tau_to_ns_and_amps_verbatim():
    ef = to_exponential_filter([0.05, -0.03], [100e-9, 3000e-9])
    assert ef == [[0.05, 100.0], [-0.03, 3000.0]]


def test_sum_length_mismatch_refused():
    with pytest.raises(ValueError, match="equal length"):
        to_exponential_filter([0.05], [1e-9, 2e-9])


def test_cascade_shape_and_scale_finite():
    out = to_exponential_filter_cascade([0.05, 0.02], [100e-9, 12e-9])
    ef = out["exponential_filter"]
    assert len(ef) == 2 and all(len(pair) == 2 for pair in ef)
    assert all(np.isfinite(a) for a, _ in ef)
    assert all(tau_ns > 0 for _, tau_ns in ef)  # tau in ns, positive
    assert np.isfinite(out["scale"])


def test_cascade_taus_are_nanoseconds():
    """A ~100 ns cascade tau lands as ~1e2 (ns), not ~1e-7 (s)."""
    out = to_exponential_filter_cascade([0.05], [100e-9])
    tau_ns = out["exponential_filter"][0][1]
    assert 1.0 < tau_ns < 1e5
