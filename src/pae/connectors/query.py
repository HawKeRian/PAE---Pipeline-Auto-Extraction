"""AST-based read-only SQL validation and bounded query construction."""

from __future__ import annotations

import re

from sqlglot import exp, parse
from sqlglot.errors import ParseError

from pae.connectors.models import DatabaseType
from pae.persistence.errors import UnsafeDatabaseQuery

_DIALECT = {"postgresql": "postgres", "mysql": "mysql", "sql_server": "tsql"}
_IDENTIFIER = re.compile(r"^[A-Za-z_][A-Za-z0-9_$]*$")
_MUTATING_NODES = (
    exp.Alter,
    exp.Command,
    exp.Create,
    exp.Delete,
    exp.Drop,
    exp.Insert,
    exp.Merge,
    exp.Transaction,
    exp.Update,
)
_UNSAFE_FUNCTIONS = {
    "benchmark",
    "dblink_connect",
    "load_file",
    "lo_import",
    "nextval",
    "openrowset",
    "pg_ls_dir",
    "pg_read_file",
    "set_config",
    "setval",
    "sleep",
}


def validate_read_only_query(query: str, database_type: DatabaseType) -> str:
    normalized = query.strip().removesuffix(";").strip()
    try:
        statements = parse(normalized, read=_DIALECT[database_type])
    except ParseError as exc:
        raise UnsafeDatabaseQuery("The custom query is not valid SQL.") from exc
    if len(statements) != 1 or not isinstance(statements[0], exp.Query):
        raise UnsafeDatabaseQuery("Exactly one read-only SELECT query is required.")
    statement = statements[0]
    if statement.find(*_MUTATING_NODES) or statement.find(exp.Into):
        raise UnsafeDatabaseQuery("The custom query may not modify data or database objects.")
    if statement.find(exp.Lock):
        raise UnsafeDatabaseQuery("Locking SELECT statements are not allowed.")
    functions = {
        (node.name if isinstance(node, exp.Anonymous) else node.sql_name()).lower()
        for node in statement.walk()
        if isinstance(node, exp.Func)
    }
    if functions & _UNSAFE_FUNCTIONS:
        raise UnsafeDatabaseQuery("The custom query calls a function that is not allowed.")
    return normalized


def quote_identifier(value: str, database_type: DatabaseType) -> str:
    if not _IDENTIFIER.fullmatch(value):
        raise UnsafeDatabaseQuery("Schema and object names must use safe identifiers.")
    if database_type == "mysql":
        return f"`{value}`"
    if database_type == "sql_server":
        return f"[{value}]"
    return f'"{value}"'


def table_select(database_type: DatabaseType, schema_name: str | None, object_name: str) -> str:
    object_sql = quote_identifier(object_name, database_type)
    if schema_name:
        object_sql = f"{quote_identifier(schema_name, database_type)}.{object_sql}"
    return f"SELECT * FROM {object_sql}"


def bounded_select(query: str, database_type: DatabaseType, limit: int) -> str:
    if database_type == "sql_server":
        return f"SELECT TOP ({limit + 1}) * FROM ({query}) AS pae_source"
    return f"SELECT * FROM ({query}) AS pae_source LIMIT {limit + 1}"
