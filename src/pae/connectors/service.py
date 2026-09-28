"""Orchestration for secure, cancellable, bounded database reads."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from contextlib import suppress
from typing import TypeVar

from pae.connectors.drivers import DatabaseDriverFactory, DatabaseSession
from pae.connectors.models import (
    DatabaseCatalog,
    DatabaseConnectionConfig,
    DatabaseSample,
    DatabaseSampleRequest,
)
from pae.connectors.network import DatabaseNetworkPolicy
from pae.connectors.query import bounded_select, table_select, validate_read_only_query
from pae.connectors.secrets import SecretResolver
from pae.persistence.errors import (
    ApplicationError,
    DatabaseConnectionFailed,
    DatabaseQueryTimeout,
)

ResultT = TypeVar("ResultT")


class DatabaseConnectorService:
    def __init__(
        self,
        driver_factory: DatabaseDriverFactory,
        secret_resolver: SecretResolver,
        network_policy: DatabaseNetworkPolicy,
        *,
        max_sample_rows: int = 10_000,
        default_timeout_seconds: int = 30,
    ) -> None:
        self.driver_factory = driver_factory
        self.secret_resolver = secret_resolver
        self.network_policy = network_policy
        self.max_sample_rows = max_sample_rows
        self.default_timeout_seconds = default_timeout_seconds

    async def _connect(self, config: DatabaseConnectionConfig) -> DatabaseSession:
        await self.network_policy.validate(config.host, config.port)
        credential = self.secret_resolver.resolve(config.connection_ref)
        try:
            return await asyncio.wait_for(
                self.driver_factory.connect(config, credential),
                timeout=self.default_timeout_seconds,
            )
        except ApplicationError:
            raise
        except TimeoutError as exc:
            raise DatabaseQueryTimeout("The database connection timed out.") from exc
        except Exception as exc:
            raise DatabaseConnectionFailed(
                "The database connection failed. Verify the host, TLS, account, and secret."
            ) from exc

    @staticmethod
    async def _close(session: DatabaseSession) -> None:
        with suppress(Exception):
            await session.close()

    async def _run(
        self,
        config: DatabaseConnectionConfig,
        operation: Callable[[DatabaseSession], Awaitable[ResultT]],
        timeout: int,
    ) -> ResultT:
        session = await self._connect(config)
        try:
            task = operation(session)
            return await asyncio.wait_for(task, timeout=timeout)
        except TimeoutError as exc:
            await session.cancel()
            raise DatabaseQueryTimeout(
                "The database operation exceeded its timeout and was cancelled."
            ) from exc
        except asyncio.CancelledError:
            await session.cancel()
            raise
        except ApplicationError:
            raise
        except Exception as exc:
            raise DatabaseConnectionFailed(
                "The database operation failed. Verify read-only access and source settings."
            ) from exc
        finally:
            await self._close(session)

    async def test_connection(self, config: DatabaseConnectionConfig) -> None:
        async def operation(session: DatabaseSession) -> None:
            await session.test_read_only()

        await self._run(config, operation, self.default_timeout_seconds)

    async def catalog(self, config: DatabaseConnectionConfig) -> DatabaseCatalog:
        async def operation(session: DatabaseSession) -> DatabaseCatalog:
            await session.test_read_only()
            return await session.catalog()

        result = await self._run(config, operation, self.default_timeout_seconds)
        assert isinstance(result, DatabaseCatalog)
        return result

    async def sample(self, request: DatabaseSampleRequest) -> DatabaseSample:
        limit = min(request.sample_limit, self.max_sample_rows)
        if request.read_only_query:
            query = validate_read_only_query(
                request.read_only_query, request.connection.database_type
            )
        else:
            assert request.object_name is not None
            query = table_select(
                request.connection.database_type, request.schema_name, request.object_name
            )
        bounded = bounded_select(query, request.connection.database_type, limit)

        async def operation(session: DatabaseSession) -> DatabaseSample:
            await session.test_read_only()
            result = await session.query(bounded)
            rows = result.rows[:limit]
            return DatabaseSample(
                columns=result.columns,
                rows=tuple(dict(zip(result.columns, row, strict=True)) for row in rows),
                truncated=len(result.rows) > limit,
                source=request.connection.safe_summary(),
            )

        result = await self._run(request.connection, operation, request.timeout_seconds)
        assert isinstance(result, DatabaseSample)
        return result
