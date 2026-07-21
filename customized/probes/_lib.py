"""Shared helpers for probes. No qualibrate imports."""

from typing import Callable, List, Optional

import xarray as xr
from qualang_tools.multi_user import qm_session
from qualang_tools.results import progress_counter
from qualibration_libs.core import BatchableList
from qualibration_libs.data import XarrayDataFetcher


def select_qubits(machine, names: Optional[List[str]] = None, *, multiplexed: bool = False) -> BatchableList:
    """Node-free replacement for `qualibration_libs.parameters.get_qubits(node)`.

    Selects qubits from the machine by name (or `machine.active_qubits` when
    `names` is None/empty) and wraps them in the same `BatchableList` the
    qualibrate helper produces, so probes can iterate `qubits.batch()` /
    `qubits.get_names()` identically in both shells.
    """
    if not names:
        qubits = machine.active_qubits
    else:
        qubits = [machine.qubits[q] for q in names]
    if multiplexed:
        batched_groups = [list(range(len(qubits)))]
    else:
        batched_groups = [[i] for i in range(len(qubits))]
    return BatchableList(qubits, batched_groups)


def acquire(
    machine,
    prog,
    sweep_axes,
    *,
    num_shots: int,
    timeout: float,
    log: Optional[Callable] = None,
    config: Optional[dict] = None,
) -> xr.Dataset:
    """Connect to the QOP, execute the program and fetch the raw xr.Dataset.

    The execute-and-fetch half is identical for every swept experiment, so all
    probes share this one implementation. `config` defaults to
    `machine.generate_config()`; pass an explicit config when the program needs a
    pre-built one (e.g. a baked config carrying baking ops the fresh config lacks).
    """
    qmm = machine.connect()
    try:
        qmm.close_all_quantum_machines()
    except Exception:
        pass
    config = config if config is not None else machine.generate_config()
    # Execute the QUA program only if the quantum machine is available (this is to avoid interrupting running jobs).
    with qm_session(qmm, config, timeout=timeout) as qm:
        job = qm.execute(prog)
        data_fetcher = XarrayDataFetcher(job, sweep_axes)
        for dataset in data_fetcher:
            progress_counter(
                data_fetcher.get("n", 0),
                num_shots,
                start_time=data_fetcher.t_start,
            )
        # Expose possible runtime errors
        if log:
            rep = getattr(job, "execution_report", None)
            if callable(rep):
                log(rep())
            elif rep is not None:
                log(rep)
    return dataset
