"""Opt-in integration tests for disposable MVP test database services.

Set PAE_TEST_<TYPE>_HOST/DATABASE/USER/PASSWORD (and optionally PORT/TLS_MODE) to enable each
database. These tests are intentionally skipped in the default local quality gate.
"""

from __future__ import annotations

import os

import psycopg
import pymysql  # type: ignore[import-untyped]
import pyodbc  # type: ignore[import-not-found]
import pytest
from pydantic import SecretStr

from pae.connectors.drivers import DefaultDatabaseDriverFactory
from pae.connectors.models import (
    DatabaseConnectionConfig,
    DatabaseCredential,
    DatabaseSampleRequest,
)
from pae.connectors.network import DatabaseNetworkPolicy
from pae.connectors.service import DatabaseConnectorService


class IntegrationSecretResolver:
    def __init__(self, password: str) -> None:
        self.password = password

    def resolve(self, reference: str) -> DatabaseCredential:
        return DatabaseCredential(password=SecretStr(self.password))


def integration_config(database_type: str) -> tuple[DatabaseConnectionConfig, str] | None:
    prefix = f"PAE_TEST_{database_type.upper()}"
    host = os.environ.get(f"{prefix}_HOST")
    database = os.environ.get(f"{prefix}_DATABASE")
    username = os.environ.get(f"{prefix}_USER")
    password = os.environ.get(f"{prefix}_PASSWORD")
    if not all((host, database, username, password)):
        return None
    defaults = {"POSTGRESQL": 5432, "MYSQL": 3306, "SQL_SERVER": 1433}
    return (
        DatabaseConnectionConfig(
            database_type=database_type,
            host=host,
            port=int(os.environ.get(f"{prefix}_PORT", defaults[database_type.upper()])),
            database=database,
            username=username,
            connection_ref=f"secret://integration/{database_type}",
            tls_mode=os.environ.get(f"{prefix}_TLS_MODE", "require"),
        ),
        password,
    )


@pytest.mark.integration
@pytest.mark.anyio
@pytest.mark.parametrize("database_type", ["postgresql", "mysql", "sql_server"])
async def test_real_database_connector_is_read_only_and_bounded(database_type: str) -> None:
    configured = integration_config(database_type)
    if configured is None:
        pytest.skip(f"{database_type} integration environment is not configured")
    config, password = configured
    factory = DefaultDatabaseDriverFactory(connect_timeout_seconds=10, query_timeout_seconds=10)
    service = DatabaseConnectorService(
        factory,
        IntegrationSecretResolver(password),
        DatabaseNetworkPolicy((config.host,), allow_private_hosts=True),
        max_sample_rows=2,
        default_timeout_seconds=10,
    )
    await service.test_connection(config)
    sample = await service.sample(
        DatabaseSampleRequest(
            connection=config,
            read_only_query="SELECT 1 AS connector_value",
            sample_limit=1,
            timeout_seconds=10,
        )
    )
    assert sample.rows[0]["connector_value"] == 1
    assert password not in sample.model_dump_json()

    session = await factory.connect(config, DatabaseCredential(password=SecretStr(password)))
    try:
        mutation = {
            "postgresql": "CREATE TEMP TABLE pae_must_fail(id integer)",
            "mysql": "CREATE TEMPORARY TABLE pae_must_fail(id integer)",
            "sql_server": "CREATE TABLE pae_must_fail(id integer)",
        }[database_type]
        with pytest.raises((psycopg.Error, pymysql.MySQLError, pyodbc.Error)):
            await session.query(mutation)
    finally:
        await session.close()
