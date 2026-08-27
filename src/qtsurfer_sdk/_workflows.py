"""High-level workflows for :class:`AuthenticatedSession`.

Adds the parity surface with the Java / TypeScript SDKs: strategy
management, catalog, backtest, sweep, and dataset workflows — each built
on the generated ``qtsurfer-api-client`` and routed through
:meth:`AuthenticatedSession.call` for refresh-on-401.

The methods here are thin, typed wrappers. They return the generated
client's model objects directly (``AcceptedJob``, ``ReturnMap``,
``SweepRunRow``, ``DatasetCreated``, ...) so a consumer gets full typed
data without the SDK hiding the API shape.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from qtsurfer.api.client._generated.models import (
    CreateDatasetBody,
    DataSourceType,
    ExecuteBacktestBody,
    ExecuteSweepRequest,
    PrepareRequest,
    SweepSpecRequest,
)

from qtsurfer_sdk._errors import (
    QTSCompileError,
)

if TYPE_CHECKING:
    from qtsurfer_sdk._session import AuthenticatedSession


# ---------------------------------------------------------------- catalog

def exchanges(session: AuthenticatedSession):
    """List the exchanges the platform serves."""
    from qtsurfer.api.client._generated.api.exchange import list_exchanges

    return session.call(lambda c: list_exchanges.sync(client=c))


def instruments(session: AuthenticatedSession, exchange_id: str, segment: str | None = None):
    """List an exchange's instruments, optionally for a segment."""
    from qtsurfer.api.client._generated.api.exchange import (
        list_instruments,
        list_segment_instruments,
    )

    if segment:
        return session.call(
            lambda c: list_segment_instruments.sync(exchange_id, segment, client=c)
        )
    return session.call(lambda c: list_instruments.sync(exchange_id, client=c))


# -------------------------------------------------------------- strategies

def compile_strategy(session: AuthenticatedSession, source: str):
    """Compile and register a Java strategy; returns ``CompileStrategyResponse200``."""
    from qtsurfer.api.client._generated.api.strategy import get_strategy  # noqa: F401 (discovery)

    # POST /strategy takes raw text; the generated client has no typed
    # text/plain endpoint, so hit it via the session's httpx client.
    try:
        httpx_client = session.client.get_httpx_client()
    except Exception:
        httpx_client = session.client._client
    resp = httpx_client.post(
        f"{session.base_url}/strategy",
        content=source.encode(),
        headers={"Content-Type": "text/plain"},
    )
    if resp.status_code != 200:
        raise QTSCompileError(
            f"compile failed: HTTP {resp.status_code}: {resp.text[:300]}",
            status=resp.status_code,
        )
    return resp.json()


def validate_strategy(session: AuthenticatedSession, strategy_id: str):
    """Ask the platform to check a registered strategy can actually run."""
    from qtsurfer.api.client._generated.api.strategy import validate_strategy

    return session.call(lambda c: validate_strategy.sync(strategy_id, client=c))


def strategy_state(session: AuthenticatedSession, strategy_id: str):
    """Read a strategy's recorded state (incl. validation verdict)."""
    from qtsurfer.api.client._generated.api.strategy import get_strategy

    return session.call(lambda c: get_strategy.sync(strategy_id, client=c))


def list_strategies(session: AuthenticatedSession):
    """List the strategies you have registered."""
    from qtsurfer.api.client._generated.api.strategy import list_strategies

    return session.call(lambda c: list_strategies.sync(client=c))


def delete_strategy(session: AuthenticatedSession, strategy_id: str):
    """Release a registered strategy."""
    from qtsurfer.api.client._generated.api.strategy import delete_strategy

    return session.call(lambda c: delete_strategy.sync(strategy_id, client=c))


def get_strategy_code(session: AuthenticatedSession, strategy_id: str) -> str:
    """Read back the exact source registered for a strategy."""
    from qtsurfer.api.client._generated.api.strategy import get_strategy_code

    resp = session.call(lambda c: get_strategy_code.sync(strategy_id, client=c))
    return resp.code if resp is not None else ""


# ---------------------------------------------------------------- backtest

def prepare(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str | DataSourceType = "ticker",
    instrument: str | None = None,
    dataset_id: str | None = None,
    from_: str,
    to: str,
    cadence: str | None = None,
):
    """Enqueue a prepare task; returns the ``AcceptedJob`` with ``job_id``.

    Pass ``dataset_id`` instead of ``instrument`` for ``exchangeId=user``.
    """
    from qtsurfer.api.client._generated.api.backtesting import prepare_backtest
    from qtsurfer.api.client._generated.models import PrepareRequestCadence

    body_kwargs: dict[str, Any] = {}
    if instrument:
        body_kwargs["instrument"] = instrument
    if dataset_id:
        body_kwargs["dataset_id"] = dataset_id
    if cadence:
        body_kwargs["cadence"] = PrepareRequestCadence(cadence)
    body = PrepareRequest(from_=from_, to=to, **body_kwargs)
    ds = DataSourceType(type_)
    return session.call(lambda c: prepare_backtest.sync(exchange_id, ds, client=c, body=body))


def prepare_status(session: AuthenticatedSession, *, exchange_id: str, type_: str, job_id: str):
    """Poll a prepare job; returns ``PrepareJobState``."""
    from qtsurfer.api.client._generated.api.backtesting import get_prepare_status

    ds = DataSourceType(type_)
    return session.call(lambda c: get_prepare_status.sync(exchange_id, ds, job_id, client=c))


def execute(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    prepare_job_id: str,
    strategy_id: str,
    store_signals: bool = False,
):
    """Run a compiled strategy over a prepared dataset; returns ``AcceptedJob``."""
    from qtsurfer.api.client._generated.api.backtesting import execute_backtest

    body = ExecuteBacktestBody(
        prepare_job_id=prepare_job_id,
        strategy_id=strategy_id,
        store_signals=store_signals,
    )
    ds = DataSourceType(type_)
    return session.call(lambda c: execute_backtest.sync(exchange_id, ds, client=c, body=body))


def backtest_result(session: AuthenticatedSession, *, exchange_id: str, type_: str, job_id: str):
    """Read an execution's result state/metrics.

    Returns a raw ``httpx.Response`` (JSON) rather than the generated
    ``sync``/``sync_detailed`` value. The generated parser calls
    ``ResultMap.from_dict`` even while a job is still ``202``-running — the
    partial ``results`` body lacks fields (e.g. ``strategyId``) and the
    parser raises ``KeyError``. Raw httpx keeps the ``202``/``200`` +
    ``state.status`` decision in the caller's poll loop, where it belongs.
    """
    from qtsurfer.api.client._generated.api.backtesting import get_backtest_result  # noqa: F401

    httpx_client = session.client.get_httpx_client()
    ds = DataSourceType(type_)
    ds = ds.value if hasattr(ds, "value") else str(ds)
    url = f"{session.base_url}/backtest/{exchange_id}/{ds}/execute/{job_id}"
    resp = session.call(lambda c: httpx_client.get(url))
    return resp


def cancel_backtest(session: AuthenticatedSession, *, exchange_id: str, type_: str, job_id: str):
    """Request cancellation of a running execution."""
    from qtsurfer.api.client._generated.api.backtesting import cancel_backtest

    ds = DataSourceType(type_)
    return session.call(lambda c: cancel_backtest.sync(exchange_id, ds, job_id, client=c))


# ------------------------------------------------------------------- sweep

def sweep(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    request_id: str,
    strategy_id: str,
    params: dict[str, Any],
    sampler: str = "grid",
    objective: str = "sharpe",
    samples: int | None = None,
    seed: int | None = None,
    walk_forward: dict[str, Any] | None = None,
    store_signals: bool = False,
):
    """Submit a parameter sweep; returns ``ExecuteSweepAccepted``."""
    from qtsurfer.api.client._generated.api.backtesting import execute_sweep

    spec = SweepSpecRequest(
        params=params,
        sampler=sampler,
        objective=objective,
        samples=samples,
        seed=seed,
    )
    body = ExecuteSweepRequest(
        strategy_id=strategy_id,
        sweep=spec,
        walk_forward=walk_forward,
        store_signals=store_signals,
    )
    ds = DataSourceType(type_)
    return session.call(
        lambda c: execute_sweep.sync(exchange_id, ds, request_id, client=c, body=body)
    )


def sweep_result(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    request_id: str,
    sweep_id: str,
    **params: Any,
):
    """Read a sweep's leaderboard / progress; returns ``ExecuteSweepResult``."""
    from qtsurfer.api.client._generated.api.backtesting import get_sweep_result

    ds = DataSourceType(type_)
    return session.call(
        lambda c: get_sweep_result.sync(
            exchange_id, ds, request_id, sweep_id, client=c, **params
        )
    )


def sweep_sensitivity(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    request_id: str,
    sweep_id: str,
):
    """Aggregate a sweep's rows into per-parameter marginals and heatmaps."""
    from qtsurfer.api.client._generated.api.backtesting import get_sweep_sensitivity

    ds = DataSourceType(type_)
    return session.call(
        lambda c: get_sweep_sensitivity.sync(exchange_id, ds, request_id, sweep_id, client=c)
    )


def sweep_run_equity_curve(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    request_id: str,
    sweep_id: str,
    run_ix: int,
    **params: Any,
):
    """Read one sweep trial's (retained) equity curve."""
    from qtsurfer.api.client._generated.api.backtesting import get_sweep_run_equity_curve

    ds = DataSourceType(type_)
    return session.call(
        lambda c: get_sweep_run_equity_curve.sync(
            exchange_id, ds, request_id, sweep_id, run_ix, client=c, **params
        )
    )


def cancel_sweep(
    session: AuthenticatedSession,
    *,
    exchange_id: str,
    type_: str,
    request_id: str,
    sweep_id: str,
):
    """Cancel a running sweep."""
    from qtsurfer.api.client._generated.api.backtesting import cancel_sweep

    ds = DataSourceType(type_)
    return session.call(
        lambda c: cancel_sweep.sync(exchange_id, ds, request_id, sweep_id, client=c)
    )


# ---------------------------------------------------------------- dataset

def create_dataset(
    session: AuthenticatedSession,
    *,
    name: str,
    instrument: str,
):
    """Create a dataset + an upload session; returns ``DatasetCreated`` with a presigned URL."""
    from qtsurfer.api.client._generated.api.dataset import create_dataset

    body = CreateDatasetBody(name=name, instrument=instrument)
    return session.call(lambda c: create_dataset.sync(client=c, body=body))


def list_datasets(session: AuthenticatedSession):
    """List your datasets."""
    from qtsurfer.api.client._generated.api.dataset import list_datasets

    return session.call(lambda c: list_datasets.sync(client=c))


def get_dataset(session: AuthenticatedSession, dataset_id: str):
    """Get one dataset by id."""
    from qtsurfer.api.client._generated.api.dataset import get_dataset

    return session.call(lambda c: get_dataset.sync(dataset_id, client=c))


def delete_dataset(session: AuthenticatedSession, dataset_id: str):
    """Delete a dataset (soft delete)."""
    from qtsurfer.api.client._generated.api.dataset import delete_dataset

    return session.call(lambda c: delete_dataset.sync(dataset_id, client=c))


def finalize_upload(session: AuthenticatedSession, *, dataset_id: str, upload_id: str):
    """Finalize an uploaded file and trigger ingest."""
    from qtsurfer.api.client._generated.api.dataset import finalize_dataset_upload

    return session.call(
        lambda c: finalize_dataset_upload.sync(dataset_id, upload_id, client=c)
    )


def dataset_upload(session: AuthenticatedSession, *, dataset_id: str, upload_id: str):
    """Poll an upload / ingest state."""
    from qtsurfer.api.client._generated.api.dataset import get_dataset_upload

    return session.call(
        lambda c: get_dataset_upload.sync(dataset_id, upload_id, client=c)
    )
