# LCHQMDriver

Superconducting-qubit calibration system for Quantum Machines OPX1000 hardware (MW-FEM + LF-FEM),
built on the qm-qua → QUAM → QUAlibrate stack. It mixes vendored official `qua-libs` calibration
nodes with this lab's custom `LCH_*` nodes, and is intended to become the QM reference backend for
the vendor-neutral `scqo` experiment API.

See [CLAUDE.md](CLAUDE.md) for the full architecture, conventions, and operating rules.
