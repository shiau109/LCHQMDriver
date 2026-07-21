"""Declarative field catalog for the QM backend — PURE DATA, no vendor imports.

Per INSTRUMENT category: one :class:`scqo.fieldmap.VendorBinding` per pushed
neutral field this backend realizes (where it lives on the QUAM tree, in what
unit, converted how — as a DESCRIPTION), one :class:`scqo.fieldmap.Unrealized`
per pushed field it does NOT (declared, never silent), plus the
:class:`scqo.fieldmap.VendorOnly` inventory of calibration-relevant knobs with no
neutral counterpart yet. The EXECUTABLE conversions live in ``QMReadableTransmon``
(backend.py, via customized.quam_fields + power_tools) — this module documents
them and is pinned to the implementation by ``tests/test_scqo_glue.py``
(per category: bindings | unrealized == scqo's pushed_fields; imports stay
vendor-free).

Rendered by ``scqo state --fields``; strings reach lab consoles, keep them ASCII.
"""

from __future__ import annotations

from scqo.fieldmap import Unrealized, VendorBinding, VendorOnly

FIELD_BINDINGS: dict[str, dict[str, VendorBinding]] = {
    "ReadableTransmon": {
        "readout_freq": VendorBinding(
            path="q.resonator.RF_frequency", unit="Hz"),
        "drive_freq": VendorBinding(
            path="q.f_01", unit="Hz",
            convert="a write also shifts q.xy.RF_frequency by the same delta "
                    "(quam_fields.set_drive_freq keeps the drive line on the qubit)"),
        "pi_amp": VendorBinding(
            path="q.xy.operations['x180'].amplitude", unit=""),
        "drag_beta": VendorBinding(
            path="q.xy.operations['x180_DragCosine'].alpha", unit="",
            convert="QM stores DRAG as DragCosinePulse.alpha; written on the "
                    "x180_DragCosine storage node (reference aliases follow)",
            note="calibrated by qubit_drag_equator / qubit_drag_alternating"),
        "readout_amp": VendorBinding(
            path="q.resonator.operations['readout'].amplitude", unit=""),
        "readout_power_dbm": VendorBinding(
            path="q.resonator.opx_output.full_scale_power_dbm "
                 "+ q.resonator.operations['readout'].amplitude",
            unit="dBm + amp",
            convert="solve the output chain (power_tools): SMALLEST full_scale_power_dbm "
                    "on the -11..+16 dBm grid (3 dB steps) keeping the amplitude <= 0.5; "
                    "the amplitude carries the exact residual",
            coupled=("readout_amp",),
            note="MW-FEM full-scale grid: -11..+16 dBm in 3 dB steps",
        ),
        "readout_duration_s": VendorBinding(
            path="q.resonator.operations['readout'].length", unit="ns",
            convert="seconds -> ns",
            coupled=("readout_integration_s",),
            note="positive multiples of 4 ns only (REFUSED otherwise, no silent "
                 "rounding); shrinking the pulse clamps the integration window "
                 "down with it; a custom weights list is rebuilt constant-window "
                 "around the new length (shaped/optimized weights do not survive)",
        ),
        "readout_integration_s": VendorBinding(
            path="q.resonator.operations['readout'].integration_weights", unit="ns",
            convert="window w -> constant weights [(1, w), (0, length - w)] "
                    "spanning the pulse exactly; the default reference when "
                    "w == length; integration_weights_angle applies on top, untouched",
            note="contract: <= readout_duration_s (weights cannot span past the "
                 "pulse); multiples of 4 ns. Qblox counterpart: "
                 "measure.integration_time (s)",
        ),
        "idle_flux_v": VendorBinding(
            path="q.z.<flux_point>_offset", unit="V",
            convert="the offset SELECTED by z.flux_point (joint/independent/min/"
                    "arbitrary; 'zero' reads 0 V and REFUSES writes)",
            note="which named flux point is active stays vendor config "
                 "(z.flux_point, catalogued below); the write lands on hardware "
                 "at the next initialize_qpu (every probe runs it). On a "
                 "fixed-frequency machine the qubit has no z: the field reads "
                 "unset and the roster should not declare flux_bias",
        ),
    },
    "TransmonPair": {
        "coupler_decouple_v": VendorBinding(
            path="qp.coupler.decouple_offset", unit="V",
            note="the interaction-OFF standing bias (pair_zz_coupler's product "
                 "- the ZZ zero crossing); applied when the coupler idles at "
                 "flux_point='off'",
        ),
        "coupler_interaction_v": VendorBinding(
            path="qp.coupler.interaction_offset", unit="V",
            note="the interaction-ON standing bias (gate operating point); "
                 "applied when the coupler idles at flux_point='on'",
        ),
    },
}

#: Pushed fields this backend declares it cannot realize (per category) — pushes
#: are skipped with the reason visible to doctor and ``scqo state --fields``.
#: (empty since idle_flux_v gained its real z-line realization at the pair
#: cutover; fixed-frequency machines surface it as unset, not Unrealized.)
UNREALIZED: dict[str, dict[str, Unrealized]] = {}

#: Backend-unique calibration knobs, vendor-owned and untracked by SCQO (edit in
#: the setup's state.json with QUAM tools). Each entry carries its placement-rule
#: kind (scqo state --rule): realizer / candidate / vendor / unique. Doubles as
#: the neutral-field promotion backlog (candidates pre-declare their convention).
VENDOR_ONLY: dict[str, VendorOnly] = {
    "readout_length": VendorOnly(
        path="q.resonator.operations['readout'].length", unit="ns", kind="realizer",
        doc="readout pulse length - realizes the TRACKED readout_duration_s "
            "(a direct edit silently de-calibrates it; the governed write is "
            "scqo set QUBIT.readout_duration_s=...). The integration window is "
            "NOT fused to it: readout_integration_s owns the weights support "
            "(default weights only LOOK fused - they span the pulse by reference)"),
    "readout_integration_weights": VendorOnly(
        path="q.resonator.operations['readout'].integration_weights", unit="",
        kind="realizer",
        doc="integration-weights list - its nonzero SUPPORT realizes the "
            "TRACKED readout_integration_s (governed write: scqo set "
            "QUBIT.readout_integration_s=...; the setter writes constant "
            "zero-padded weights). The SHAPE within the window stays vendor "
            "territory (a future weight-optimization node may write it; any "
            "later window write rebuilds constant weights)"),
    "time_of_flight": VendorOnly(
        path="q.resonator.time_of_flight", unit="ns", kind="vendor",
        doc="acquisition latency compensation - aligns the instrument's receive "
            "path with its own transmit path. The TOF measurement's product is "
            "written HERE, in NANOSECONDS, offline - never a neutral field. "
            "Qblox counterpart: measure.acq_delay (s)"),
    "depletion_time": VendorOnly(
        path="q.resonator.depletion_time", unit="ns", kind="vendor",
        doc="resonator ring-down wait after readout - a policy value (~several/"
            "kappa), not a calibration outcome; the punchout experiments "
            "override it per run via resonator_relaxation_time_ns"),
    "readout_upconverter_frequency": VendorOnly(
        path="q.resonator.opx_output.upconverter_frequency", unit="Hz", kind="vendor",
        doc="readout LO - the MW-FEM upconverter, PORT-level (state.json "
            "ports.mw_outputs.<con>.<fem>.<port>) and shared by everything on "
            "that output; many LO/IF splits give the SAME RF, so SCQO owns only "
            "the RF (readout_freq) and never moves the LO in a chain solve. "
            "Move it so IF = RF - LO stays in range, the port band must cover "
            "the target, and downconverter_frequency MUST move with it or "
            "demodulation breaks. Qblox counterpart: modulation_frequencies "
            "lo_freq"),
    "drive_upconverter_frequency": VendorOnly(
        path="q.xy.opx_output.upconverter_frequency", unit="Hz", kind="vendor",
        doc="drive LO - PORT-level MW-FEM upconverter, shared; keep "
            "IF = f_01 - LO in range and the port band matching"),
    "downconverter_frequency": VendorOnly(
        path="q.resonator.opx_input.downconverter_frequency", unit="Hz", kind="vendor",
        doc="receive-side downconversion LO on the MW input port (chipA: "
            "6.06 GHz, equal to the readout upconverter) - MUST track "
            "readout_upconverter_frequency or demodulation breaks; PORT-level, "
            "band-constrained. Qblox has no separate knob (NCO handles it)"),
    "full_scale_power_dbm": VendorOnly(
        path="q.resonator.opx_output.full_scale_power_dbm", unit="dBm", kind="realizer",
        doc="the coarse readout power knob (grid -11..+16 in 3 dB steps, "
            "PORT-level - shared like the LO) - it REALIZES the tracked "
            "readout_power_dbm (binding above). Change power with "
            "`scqo set QUBIT.readout_power_dbm=...` (solves the chain, keeps "
            "readout_amp coupled, recorded); a direct edit silently "
            "de-calibrates the absolute power, and any later readout_power_dbm "
            "write re-solves and overwrites a forced value"),
    "drive_full_scale_power_dbm": VendorOnly(
        path="q.xy.opx_output.full_scale_power_dbm", unit="dBm", kind="vendor",
        doc="the untracked DRIVE-chain scale that makes pi_amp portable=False "
            "(chipA: +13 dBm) - no neutral drive_power_dbm twin exists "
            "(optional future engineering). Changing it silently re-scales "
            "what every stored pi_amp means. Qblox counterpart: drive-port "
            "output_att"),
    "x180_length": VendorOnly(
        path="q.xy.operations['x180'].length", unit="ns", kind="candidate",
        doc="pi/x180 pulse length - neutral pi_duration_s candidate (seconds; "
            "chipA: 32 ns here vs 200 ns on Qblox - genuinely per-chain "
            "calibrated); multiple of 4 ns. Qblox counterpart: rxy.duration (s)"),
    "drag_alpha": VendorOnly(
        path="q.xy.operations['<gate>_DragCosine'].alpha", unit="", kind="realizer",
        doc="PER-GATE DRAG coefficient (chipA: x180 -0.94, x90 -0.50). The x180 "
            "node now REALIZES the tracked neutral drag_beta (binding above; "
            "governed write: scqo set QUBIT.drag_beta=...); the OTHER gates' "
            "alpha values remain vendor fine print edited directly. Qblox "
            "counterpart: rxy.beta (derivative scale, different math convention)"),
    "integration_weights_angle": VendorOnly(
        path="q.resonator.operations['readout'].integration_weights_angle",
        unit="rad", kind="vendor",
        doc="demodulation rotation before thresholding (RADIANS here; Qblox "
            "acq_rotation is DEGREES) - acquisition IQ frame, NO declarable "
            "reference plane, never a neutral field; invalidated by "
            "input-chain changes (mw_input gain_db). Portable traces: "
            "readout_fidelity + confusion entries"),
    "readout_threshold": VendorOnly(
        path="q.resonator.operations['readout'].threshold", unit="V", kind="vendor",
        doc="single-shot g/e discrimination threshold in demodulated VOLTS - "
            "acquisition-frame, chain-dependent (Qblox acq_threshold uses a "
            "normalized frame instead); invalidated by input-chain changes"),
    "per_gate_detuning": VendorOnly(
        path="q.xy.operations['x90_DragCosine'].detuning", unit="Hz", kind="unique",
        doc="per-gate drive detuning (chipA: -300 kHz on x90 vs 0 on x180) - "
            "no Qblox counterpart (one shared rxy op set there): experiments "
            "depending on it run ONLY on QM"),
    "rus_exit_threshold": VendorOnly(
        path="q.resonator.operations['readout'].rus_exit_threshold", unit="V",
        kind="unique",
        doc="repeat-until-success exit threshold - no Qblox counterpart: "
            "experiments touching it run ONLY on QM"),
    # ----------------------------------------------------------- qubit pairs (QCQ)
    "pair_detuning": VendorOnly(
        path="qp.detuning", unit="V", kind="candidate",
        doc="flux amplitude bringing the two qubits to equal energy (the gate "
            "resonance condition) - neutral detuning_v candidate; promoted when "
            "a scqo experiment (chevron) calibrates it"),
    "pair_moving_qubit": VendorOnly(
        path="qp.moving_qubit", unit="", kind="vendor",
        doc="which vendor side (control/target) carries the flux pulse in 2Q "
            "gates - a PER-OPERATION fact the driver reads; roster roles are "
            "high/low and never store this (settled pair-role decision)"),
    "coupler_flux_point": VendorOnly(
        path="qp.coupler.flux_point", unit="", kind="vendor",
        doc="which named coupler point idles (off/on/arbitrary/zero) - selects "
            "WHICH offset coupler_decouple_v/coupler_interaction_v realize at "
            "idle; a mode switch, not a calibration outcome"),
    "coupler_arbitrary_offset": VendorOnly(
        path="qp.coupler.arbitrary_offset", unit="V", kind="vendor",
        doc="free-form coupler bias for exploratory work - not a governed "
            "operating point (those are decouple/interaction)"),
    "coupler_settle_time": VendorOnly(
        path="qp.coupler.settle_time", unit="ns", kind="vendor",
        doc="coupler flux settle wait - an instrument-response policy value, "
            "not a calibration outcome"),
    "pair_mutual_flux_bias": VendorOnly(
        path="qp.mutual_flux_bias", unit="V", kind="vendor",
        doc="two-element per-qubit z biases for the pair's mutual idle "
            "(to_mutual_idle); vendor-owned gate plumbing"),
    "iswap_macro": VendorOnly(
        path="qp.macros['iswap'] (flux_pulse, phase_shift_control/target)", unit="",
        kind="vendor",
        doc="the iswap gate macro: flux_pulse names a coupler+control-z pulse "
            "op; the phase shifts are currently DEAD (commented out in "
            "apply()). Gate-pulse amplitudes/lengths become neutral fields "
            "only when a scqo experiment calibrates them (chevron/CZ - Phase 2b)"),
    "pair_confusion": VendorOnly(
        path="qp.confusion", unit="", kind="vendor",
        doc="4x4 two-qubit assignment confusion matrix - a stored measured "
            "artifact, DEAD to SCQO per the placement rule (never read, never "
            "written by it); portable traces live in run records"),
}
