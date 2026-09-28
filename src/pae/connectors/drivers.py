"""DB-API adapters for PostgreSQL, MySQL, and Microsoft SQL Server."""

from __future__ import annotations

import asyncio
import ssl
from collections.abc import Callable
from contextlib import suppress
from typing import Any, Protocol

import psycopg
import pymysql  # type: ignore[import-untyped]
import pyodbc  # type: ignore[import-not-found]

from pae.connectors.models import (
    DatabaseCatalog,
    DatabaseConnectionConfig,
    DatabaseCredential,
    DatabaseObject,
    QueryResult,
)
from pae.persistence.errors import DatabaseReadOnlyRequired


class DatabaseSession(Protocol):
    async def test_read_only(self) -> None: ...

    async def catalog(self) -> DatabaseCatalog: ...

    async def query(self, sql: str) -> QueryResult: ...

    async def cancel(self) -> None: ...

    async def close(self) -> None: ...


class DatabaseDriverFactory(Protocol):
    async def connect(
        self, config: DatabaseConnectionConfig, credential: DatabaseCredential
    ) -> DatabaseSession: ...


class DbApiSession:
    def __init__(self, connection: Any, database_type: str, timeout_seconds: int) -> None:
        self.connection = connection
        self.database_type = database_type
        self.timeout_seconds = timeout_seconds
        self._lock = asyncio.Lock()

    def _begin_read_only(self, cursor: Any) -> None:
        if self.database_type == "postgresql":
            cursor.execute("BEGIN READ ONLY")
            cursor.execute(f"SET LOCAL statement_timeout = {self.timeout_seconds * 1000}")
        elif self.database_type == "mysql":
            cursor.execute("START TRANSACTION READ ONLY")
            cursor.execute(f"SET SESSION MAX_EXECUTION_TIME = {self.timeout_seconds * 1000}")
        else:
            cursor.timeout = self.timeout_seconds
            cursor.execute("SET TRANSACTION ISOLATION LEVEL SNAPSHOT")

    def _rollback(self) -> None:
        with suppress(Exception):
            self.connection.rollback()

    def _execute(self, sql: str) -> QueryResult:
        cursor = self.connection.cursor()
        try:
            self._begin_read_only(cursor)
            cursor.execute(sql)
            columns = tuple(str(column[0]) for column in (cursor.description or ()))
            rows = tuple(tuple(row) for row in cursor.fetchall())
            return QueryResult(columns=columns, rows=rows)
        finally:
            cursor.close()
            self._rollback()

    async def query(self, sql: str) -> QueryResult:
        async with self._lock:
            return await asyncio.to_thread(self._execute, sql)

    async def test_read_only(self) -> None:
        if self.database_type == "sql_server":
            permission_query = (
                "SELECT COUNT(*) AS mutation_permissions FROM fn_my_permissions(NULL, "
                "'DATABASE') WHERE permission_name IN ('CONTROL', 'ALTER', 'CREATE TABLE', "
                "'INSERT', 'UPDATE', 'DELETE', 'EXECUTE')"
            )
            result = await self.query(permission_query)
            if result.rows and int(result.rows[0][0]) > 0:
                raise DatabaseReadOnlyRequired(
                    "The SQL Server account has mutation permissions; use a read-only account."
                )
            return
        await self.query("SELECT 1")

    async def catalog(self) -> DatabaseCatalog:
        if self.database_type == "sql_server":
            sql = (
                "SELECT TABLE_SCHEMA, TABLE_NAME, CASE TABLE_TYPE WHEN 'VIEW' THEN 'view' "
                "ELSE 'table' END FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
        else:
            sql = (
                "SELECT table_schema, table_name, CASE table_type WHEN 'VIEW' THEN 'view' "
                "ELSE 'table' END FROM information_schema.tables "
                "WHERE table_type IN ('BASE TABLE', 'VIEW') ORDER BY table_schema, table_name"
            )
        result = await self.query(sql)
        objects = tuple(
            DatabaseObject(schema_name=str(row[0]), object_name=str(row[1]), object_type=row[2])
            for row in result.rows
        )
        return DatabaseCatalog(
            schemas=tuple(dict.fromkeys(item.schema_name for item in objects)), objects=objects
        )

    async def cancel(self) -> None:
        cancel = getattr(self.connection, "cancel", None)
        if callable(cancel):
            await asyncio.to_thread(cancel)
        else:
            await self.close()

    async def close(self) -> None:
        if not getattr(self.connection, "closed", False):
            await asyncio.to_thread(self.connection.close)


class DefaultDatabaseDriverFactory:
    def __init__(self, *, connect_timeout_seconds: int = 10, query_timeout_seconds: int = 30):
        self.connect_timeout_seconds = connect_timeout_seconds
        self.query_timeout_seconds = query_timeout_seconds

    async def connect(
        self, config: DatabaseConnectionConfig, credential: DatabaseCredential
    ) -> DatabaseSession:
        factories: dict[str, Callable[[], Any]] = {
            "postgresql": lambda: self._postgresql(config, credential),
            "mysql": lambda: self._mysql(config, credential),
            "sql_server": lambda: self._sql_server(config, credential),
        }
        connection = await asyncio.to_thread(factories[config.database_type])
        return DbApiSession(connection, config.database_type, self.query_timeout_seconds)

    def _postgresql(self, config: DatabaseConnectionConfig, credential: DatabaseCredential) -> Any:
        sslmode = {
            "require": "require",
            "verify_ca": "verify-ca",
            "verify_identity": "verify-full",
        }[config.tls_mode]
        return psycopg.connect(
            host=config.host,
            port=config.port,
            dbname=config.database,
            user=config.username,
            password=credential.password.get_secret_value(),
            sslmode=sslmode,
            connect_timeout=self.connect_timeout_seconds,
            autocommit=False,
        )

    def _mysql(self, config: DatabaseConnectionConfig, credential: DatabaseCredential) -> Any:
        if config.tls_mode == "require":
            ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        else:
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = config.tls_mode == "verify_identity"
        return pymysql.connect(
            host=config.host,
            port=config.port,
            database=config.database,
            user=config.username,
            password=credential.password.get_secret_value(),
            connect_timeout=self.connect_timeout_seconds,
            read_timeout=self.query_timeout_seconds,
            write_timeout=self.query_timeout_seconds,
            ssl=ssl_context,
            autocommit=False,
        )

    def _sql_server(self, config: DatabaseConnectionConfig, credential: DatabaseCredential) -> Any:
        trust_certificate = "yes" if config.tls_mode == "require" else "no"
        connection_string = (
            "DRIVER={ODBC Driver 18 for SQL Server};"
            f"SERVER={config.host},{config.port};DATABASE={config.database};UID={config.username};"
            f"PWD={credential.password.get_secret_value()};Encrypt=yes;"
            f"TrustServerCertificate={trust_certificate};ApplicationIntent=ReadOnly"
        )
        return pyodbc.connect(
            connection_string, timeout=self.connect_timeout_seconds, autocommit=False
        )
