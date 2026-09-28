"""Contract tests for secure and bounded database source connectors."""

from __future__ import annotations

import asyncio
import socket
from typing import Any

import pytest
from pydantic import SecretStr, ValidationError

from pae.connectors.drivers import DatabaseDriverFactory, DatabaseSession, DbApiSession
from pae.connectors.models import (
    DatabaseCatalog,
    DatabaseConnectionConfig,
    DatabaseCredential,
    DatabaseObject,
    DatabaseSampleRequest,
    QueryResult,
)
from pae.connectors.network import DatabaseNetworkPolicy
from pae.connectors.query import (
    bounded_select,
    quote_identifier,
    table_select,
    validate_read_only_query,
)
from pae.connectors.secrets import EnvironmentSecretResolver, SecretResolver
from pae.connectors.service import DatabaseConnectorService
from pae.persistence.errors import (
    DatabaseConnectionFailed,
    DatabaseHostRejected,
    DatabaseQueryTimeout,
    DatabaseReadOnlyRequired,
    SecretReferenceUnavailable,
    UnsafeDatabaseQuery,
)


def connection(database_type: str = "postgresql") -> DatabaseConnectionConfig:
    ports = {"postgresql": 5432, "mysql": 3306, "sql_server": 1433}
    return DatabaseConnectionConfig(
        database_type=database_type,
        host="db.example.com",
        port=ports[database_type],
        database="analytics",
        username="reader",
        connection_ref="secret://warehouse/read-only",
    )


class FakeResolver(SecretResolver):
    def resolve(self, reference: str) -> DatabaseCredential:
        assert reference == "secret://warehouse/read-only"
        return DatabaseCredential(password=SecretStr("not-returned"))


class FakeNetworkPolicy(DatabaseNetworkPolicy):
    def __init__(self) -> None:
        super().__init__(("db.example.com",), allow_private_hosts=False)
        self.validated = False

    async def validate(self, host: str, port: int) -> None:
        self.validated = True


class FakeSession(DatabaseSession):
    def __init__(
        self,
        *,
        result: QueryResult | None = None,
        delay: float = 0,
        failure: Exception | None = None,
    ) -> None:
        self.result = result or QueryResult(columns=("id",), rows=((1,), (2,), (3,)))
        self.delay = delay
        self.failure = failure
        self.queries: list[str] = []
        self.tested = False
        self.cancelled = False
        self.closed = False
        self.query_started = asyncio.Event()

    async def test_read_only(self) -> None:
        self.tested = True
        if self.failure:
            raise self.failure

    async def catalog(self) -> DatabaseCatalog:
        return DatabaseCatalog(
            schemas=("public",),
            objects=(
                DatabaseObject(schema_name="public", object_name="orders", object_type="table"),
            ),
        )

    async def query(self, sql: str) -> QueryResult:
        self.queries.append(sql)
        self.query_started.set()
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.failure:
            raise self.failure
        return self.result

    async def cancel(self) -> None:
        self.cancelled = True

    async def close(self) -> None:
        self.closed = True


class FakeFactory(DatabaseDriverFactory):
    def __init__(self, session: FakeSession, *, failure: Exception | None = None) -> None:
        self.session = session
        self.failure = failure

    async def connect(
        self, config: DatabaseConnectionConfig, credential: DatabaseCredential
    ) -> DatabaseSession:
        assert credential.password.get_secret_value() == "not-returned"
        if self.failure:
            raise self.failure
        return self.session


def service(session: FakeSession, *, failure: Exception | None = None) -> DatabaseConnectorService:
    return DatabaseConnectorService(
        FakeFactory(session, failure=failure),
        FakeResolver(),
        FakeNetworkPolicy(),
        max_sample_rows=2,
        default_timeout_seconds=1,
    )


@pytest.mark.parametrize("database_type", ["postgresql", "mysql", "sql_server"])
def test_read_only_select_and_dialect_limits(database_type: str) -> None:
    assert validate_read_only_query("SELECT id FROM orders;", database_type) == (
        "SELECT id FROM orders"
    )
    query = table_select(database_type, "sales", "orders")
    bounded = bounded_select(query, database_type, 10)
    if database_type == "sql_server":
        assert "TOP (11)" in bounded and "[sales].[orders]" in bounded
    elif database_type == "mysql":
        assert bounded.endswith("LIMIT 11") and "`sales`.`orders`" in bounded
    else:
        assert bounded.endswith("LIMIT 11") and '"sales"."orders"' in bounded


@pytest.mark.parametrize(
    "query",
    [
        "UPDATE orders SET amount = 0",
        "DELETE FROM orders",
        "CREATE TABLE stolen(id int)",
        "SELECT 1; SELECT 2",
        "SELECT * INTO copied FROM orders",
        "SELECT * FROM orders FOR UPDATE",
        "SELECT pg_read_file('/etc/passwd')",
        "SELECT SLEEP(20)",
    ],
)
def test_mutating_locking_multi_statement_and_unsafe_functions_are_rejected(query: str) -> None:
    with pytest.raises(UnsafeDatabaseQuery):
        validate_read_only_query(query, "postgresql")


def test_connection_models_reject_embedded_connection_fragments() -> None:
    with pytest.raises(ValidationError, match="connection string"):
        connection().model_copy(update={"host": "db;password=bad"}).model_validate(
            connection().model_copy(update={"host": "db;password=bad"}).model_dump()
        )
    with pytest.raises(ValidationError, match="exactly one"):
        DatabaseSampleRequest(
            connection=connection(), object_name="orders", read_only_query="SELECT 1"
        )
    with pytest.raises(UnsafeDatabaseQuery):
        quote_identifier("orders;drop", "postgresql")
    summary = connection().safe_summary()
    assert summary["host"] == summary["database"] == summary["username"] == "***"
    assert summary["connection_ref"] == "secret://***"


@pytest.mark.anyio
async def test_service_tests_catalogs_and_returns_bounded_masked_sample() -> None:
    session = FakeSession()
    connector = service(session)
    await connector.test_connection(connection())
    assert session.tested and session.closed

    catalog_session = FakeSession()
    catalog = await service(catalog_session).catalog(connection())
    assert catalog.schemas == ("public",)
    assert catalog.objects[0].object_type == "table"

    sample_session = FakeSession()
    sample = await service(sample_session).sample(
        DatabaseSampleRequest(
            connection=connection(), schema_name="public", object_name="orders", sample_limit=10
        )
    )
    assert sample.rows == ({"id": 1}, {"id": 2})
    assert sample.truncated is True
    assert "LIMIT 3" in sample_session.queries[0]
    assert "not-returned" not in sample.model_dump_json()
    assert "db.example.com" not in sample.model_dump_json()
    assert sample_session.closed


@pytest.mark.anyio
async def test_custom_query_is_wrapped_and_connection_errors_are_sanitized() -> None:
    session = FakeSession(result=QueryResult(columns=("total",), rows=((10,),)))
    sample = await service(session).sample(
        DatabaseSampleRequest(connection=connection("mysql"), read_only_query="SELECT 10 AS total")
    )
    assert sample.rows == ({"total": 10},)
    assert "SELECT 10 AS total" in session.queries[0]

    with pytest.raises(DatabaseConnectionFailed, match="host, TLS") as captured:
        await service(FakeSession(), failure=RuntimeError("password=leaked")).test_connection(
            connection()
        )
    assert "leaked" not in str(captured.value)


@pytest.mark.anyio
async def test_timeout_and_caller_cancellation_cancel_and_close_session() -> None:
    timed = FakeSession(delay=0.05)
    connector = service(timed)
    request = DatabaseSampleRequest(
        connection=connection(), object_name="orders", timeout_seconds=1
    )
    with pytest.raises(DatabaseQueryTimeout):
        await connector._run(request.connection, lambda session: session.query("SELECT 1"), 0.001)
    assert timed.cancelled and timed.closed

    cancelled = FakeSession(delay=1)
    task = asyncio.create_task(
        service(cancelled).sample(
            DatabaseSampleRequest(connection=connection(), object_name="orders")
        )
    )
    await asyncio.wait_for(cancelled.query_started.wait(), timeout=1)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert cancelled.cancelled and cancelled.closed


@pytest.mark.anyio
async def test_network_policy_blocks_unlisted_and_private_hosts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    policy = DatabaseNetworkPolicy(("allowed.example",), allow_private_hosts=True)
    with pytest.raises(DatabaseHostRejected, match="allowlist"):
        await policy.validate("other.example", 5432)

    monkeypatch.setattr(
        socket,
        "getaddrinfo",
        lambda *args, **kwargs: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.2", 5432))],
    )
    await policy.validate("allowed.example", 5432)
    blocked = DatabaseNetworkPolicy((), allow_private_hosts=False)
    with pytest.raises(DatabaseHostRejected, match="private or reserved"):
        await blocked.validate("private.example", 5432)


def test_environment_secret_resolver_never_returns_plain_text_in_repr(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    resolver = EnvironmentSecretResolver()
    monkeypatch.setenv("PAE_SECRET_WAREHOUSE_READ_ONLY", "database-password")
    credential = resolver.resolve("secret://warehouse/read-only")
    assert credential.password.get_secret_value() == "database-password"
    assert "database-password" not in repr(credential)
    monkeypatch.delenv("PAE_SECRET_WAREHOUSE_READ_ONLY")
    with pytest.raises(SecretReferenceUnavailable) as captured:
        resolver.resolve("secret://warehouse/read-only")
    assert "database-password" not in str(captured.value.details)


class FakeCursor:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.rows = rows
        self.description = (("value",),)
        self.executed: list[str] = []
        self.timeout = 0
        self.closed = False

    def execute(self, sql: str) -> None:
        self.executed.append(sql)

    def fetchall(self) -> list[tuple[Any, ...]]:
        return self.rows

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self, rows: list[tuple[Any, ...]]) -> None:
        self.cursor_value = FakeCursor(rows)
        self.closed = False
        self.rolled_back = False
        self.cancelled = False

    def cursor(self) -> FakeCursor:
        return self.cursor_value

    def rollback(self) -> None:
        self.rolled_back = True

    def cancel(self) -> None:
        self.cancelled = True

    def close(self) -> None:
        self.closed = True


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("database_type", "begin_fragment"),
    [
        ("postgresql", "BEGIN READ ONLY"),
        ("mysql", "START TRANSACTION READ ONLY"),
        ("sql_server", "SNAPSHOT"),
    ],
)
async def test_dbapi_session_enforces_read_only_setup(
    database_type: str, begin_fragment: str
) -> None:
    raw = FakeConnection([(1,)])
    session = DbApiSession(raw, database_type, 5)
    result = await session.query("SELECT 1")
    assert result.rows == ((1,),)
    assert any(begin_fragment in query for query in raw.cursor_value.executed)
    assert raw.rolled_back and raw.cursor_value.closed
    await session.cancel()
    assert raw.cancelled
    await session.close()
    assert raw.closed


@pytest.mark.anyio
async def test_sql_server_rejects_account_with_mutation_permissions() -> None:
    raw = FakeConnection([(1,)])
    session = DbApiSession(raw, "sql_server", 5)
    with pytest.raises(DatabaseReadOnlyRequired):
        await session.test_read_only()
