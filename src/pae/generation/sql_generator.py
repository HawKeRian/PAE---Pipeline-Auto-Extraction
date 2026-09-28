"""Read-only, parameterized SQL generation for the three MVP dialects."""

# ruff: noqa: E501 -- long SQL fragments remain easier to audit as complete expressions.

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

import sqlglot
from sqlglot.errors import ParseError

from pae.domain.enums import (
    ArtifactStatus,
    DataType,
    OutputFormat,
    SqlDialect,
    TargetLanguage,
    TransformationKind,
    ValidationKind,
)
from pae.domain.models import DatabaseSource, PipelineSpecification, TransformationRule
from pae.generation.models import GeneratedSqlPackage, PackageValidation
from pae.persistence.errors import InvalidSpecificationRule, UnsupportedCapability
from pae.runtime_core import execute

_READ_DIALECT = {
    SqlDialect.POSTGRESQL: "postgres",
    SqlDialect.MYSQL: "mysql",
    SqlDialect.SQL_SERVER: "tsql",
}

_CAST_TYPES: dict[SqlDialect, dict[DataType, str]] = {
    SqlDialect.POSTGRESQL: {
        DataType.STRING: "TEXT",
        DataType.INTEGER: "BIGINT",
        DataType.DECIMAL: "DECIMAL(38, 10)",
        DataType.BOOLEAN: "BOOLEAN",
        DataType.DATE: "DATE",
        DataType.DATETIME: "TIMESTAMPTZ",
        DataType.JSON: "JSONB",
    },
    SqlDialect.MYSQL: {
        DataType.STRING: "CHAR",
        DataType.INTEGER: "SIGNED",
        DataType.DECIMAL: "DECIMAL(38, 10)",
        DataType.BOOLEAN: "UNSIGNED",
        DataType.DATE: "DATE",
        DataType.DATETIME: "DATETIME",
        DataType.JSON: "JSON",
    },
    SqlDialect.SQL_SERVER: {
        DataType.STRING: "NVARCHAR(MAX)",
        DataType.INTEGER: "BIGINT",
        DataType.DECIMAL: "DECIMAL(38, 10)",
        DataType.BOOLEAN: "BIT",
        DataType.DATE: "DATE",
        DataType.DATETIME: "DATETIMEOFFSET",
        DataType.JSON: "NVARCHAR(MAX)",
    },
}


def _string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        raise InvalidSpecificationRule("Rule parameter must be a list.")
    return [str(item) for item in value]


@dataclass
class _SqlBuild:
    dialect: SqlDialect
    parameters: dict[str, object] = field(default_factory=dict)
    stages: list[str] = field(default_factory=list)
    columns: list[str] = field(default_factory=list)
    order_by: list[str] = field(default_factory=list)

    def quote(self, identifier: str) -> str:
        if not identifier or "\x00" in identifier:
            raise InvalidSpecificationRule("SQL identifier is empty or unsafe.")
        if self.dialect is SqlDialect.MYSQL:
            return f"`{identifier.replace('`', '``')}`"
        return f'"{identifier.replace(chr(34), chr(34) * 2)}"'

    def parameter(self, value: object) -> str:
        name = f"p{len(self.parameters) + 1}"
        self.parameters[name] = value
        return f":{name}"

    @property
    def current(self) -> str:
        return f"step_{len(self.stages) - 1}"

    def add(self, body: str) -> None:
        self.stages.append(f"step_{len(self.stages)} AS (\n{body}\n)")

    def projection(self, replacements: dict[str, str]) -> str:
        return ",\n    ".join(
            f"{replacements.get(name, self.quote(name))} AS {self.quote(name)}"
            for name in self.columns
        )


class SqlGenerator:
    """Compile a confirmed database specification to a read-only SQL package."""

    def generate(self, specification: PipelineSpecification) -> GeneratedSqlPackage:
        dialect = specification.target.sql_dialect
        if specification.target.language is not TargetLanguage.SQL or dialect is None:
            raise UnsupportedCapability("The SQL generator requires a SQL target and dialect.")
        if specification.output.format is not OutputFormat.SQL_RESULT:
            raise UnsupportedCapability("SQL targets return a read-only SQL result contract.")
        if len(specification.sources) != 1 or not isinstance(
            specification.sources[0], DatabaseSource
        ):
            raise UnsupportedCapability(
                "SQL generation reads one confirmed database source; file inputs are unsupported."
            )
        if specification.joins or any(
            rule.kind is TransformationKind.JOIN for rule in specification.transformations
        ):
            raise UnsupportedCapability("Multi-source Join is Deferred for SQL generation.")

        source = specification.sources[0]
        expected_database = {
            SqlDialect.POSTGRESQL: "postgresql",
            SqlDialect.MYSQL: "mysql",
            SqlDialect.SQL_SERVER: "sql_server",
        }[dialect]
        if source.database_type != expected_database:
            raise UnsupportedCapability(
                "The SQL dialect must match the confirmed database source type."
            )
        build = _SqlBuild(dialect=dialect)
        selected = [item for item in specification.fields if item.selected]
        build.columns = [item.target_name for item in selected]
        initial = ",\n    ".join(
            f"src.{build.quote(item.source_name)} AS {build.quote(item.target_name)}"
            for item in selected
        )
        source_sql = self._source_sql(build, source)
        build.add(f"SELECT\n    {initial}\nFROM {source_sql} AS src")
        for rule in sorted(specification.transformations, key=lambda item: item.order):
            if rule.enabled:
                self._apply_rule(build, rule)
        final_order = f"\nORDER BY {', '.join(build.order_by)}" if build.order_by else ""
        stage_sql = ",\n".join(build.stages)
        query = f"WITH\n{stage_sql}\nSELECT * FROM {build.current}{final_order};\n"
        validation_queries = self._validations(build, specification)
        self._validate_read_only(query, dialect)
        for statement in validation_queries:
            self._validate_read_only(statement, dialect)
        files = {
            "pipeline.sql": query,
            "validation_queries.sql": "\n\n".join(validation_queries)
            + ("\n" if validation_queries else ""),
            "parameters.json": json.dumps(
                build.parameters, ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            "README.md": self._readme(specification, dialect),
        }
        payload = "".join(f"{name}\0{files[name]}\0" for name in sorted(files))
        return GeneratedSqlPackage(
            dialect=dialect,
            files=files,
            parameters=build.parameters,
            checksum=hashlib.sha256(payload.encode()).hexdigest(),
        )

    @staticmethod
    def syntax_validate(package: GeneratedSqlPackage) -> PackageValidation:
        try:
            for name in ("pipeline.sql", "validation_queries.sql"):
                content = package.files[name].strip()
                if content:
                    sqlglot.parse(content, read=_READ_DIALECT[package.dialect])
        except ParseError as exc:
            raise InvalidSpecificationRule(
                f"Generated {package.dialect.value} SQL is invalid."
            ) from exc
        return PackageValidation(
            status=ArtifactStatus.SYNTAX_VALIDATED,
            syntax_valid=True,
            sample_matches_preview=False,
            checked_files=("pipeline.sql", "validation_queries.sql"),
        )

    @staticmethod
    def sample_validate(
        package: GeneratedSqlPackage,
        specification: PipelineSpecification,
        rows: tuple[dict[str, Any], ...],
        executor: Callable[[str, dict[str, object]], list[dict[str, Any]]],
    ) -> PackageValidation:
        """Execute on a caller-owned disposable database and compare with Preview semantics."""

        SqlGenerator.syntax_validate(package)
        actual = executor(package.files["pipeline.sql"], package.parameters)
        expected = execute(specification.model_dump(mode="json"), list(rows))["output_rows"]
        matches = actual == expected
        return PackageValidation(
            status=ArtifactStatus.SAMPLE_TESTED if matches else ArtifactStatus.SYNTAX_VALIDATED,
            syntax_valid=True,
            sample_matches_preview=matches,
            checked_files=("pipeline.sql", "validation_queries.sql"),
        )

    @staticmethod
    def _source_sql(build: _SqlBuild, source: DatabaseSource) -> str:
        if source.read_only_query:
            statements = sqlglot.parse(source.read_only_query, read=_READ_DIALECT[build.dialect])
            if (
                len(statements) != 1
                or statements[0] is None
                or statements[0].key not in {"select", "union", "with"}
            ):
                raise InvalidSpecificationRule("SQL source query must be read-only SELECT.")
            return f"({source.read_only_query.rstrip(';')})"
        assert source.object_name is not None
        table = build.quote(source.object_name)
        return f"{build.quote(source.schema_name)}.{table}" if source.schema_name else table

    def _apply_rule(self, build: _SqlBuild, rule: TransformationRule) -> None:
        kind = rule.kind
        inputs = list(rule.inputs)
        parameters = rule.parameters
        if kind is TransformationKind.INCLUDE:
            build.columns = [name for name in build.columns if name in inputs]
            if not build.columns:
                raise InvalidSpecificationRule("Include must retain at least one column.")
            self._select_stage(build)
        elif kind is TransformationKind.EXCLUDE:
            build.columns = [name for name in build.columns if name not in inputs]
            if not build.columns:
                raise InvalidSpecificationRule("Exclude cannot remove every column.")
            self._select_stage(build)
        elif kind is TransformationKind.RENAME:
            if rule.output is None:
                raise InvalidSpecificationRule(f"Rule {rule.rule_id} requires output.")
            source = inputs[0]
            projection = ",\n    ".join(
                f"{build.quote(name)} AS {build.quote(rule.output if name == source else name)}"
                for name in build.columns
            )
            previous = build.current
            build.add(f"SELECT\n    {projection}\nFROM {previous}")
            build.columns = [rule.output if name == source else name for name in build.columns]
            build.order_by = [
                item.replace(build.quote(source), build.quote(rule.output))
                for item in build.order_by
            ]
        elif kind is TransformationKind.CAST:
            target = DataType(str(parameters["type"]))
            expression = f"CAST({build.quote(inputs[0])} AS {_CAST_TYPES[build.dialect][target]})"
            self._replace_stage(build, inputs[0], expression)
        elif kind is TransformationKind.FILTER:
            predicate = self._filter(
                build, inputs[0], str(parameters["operator"]), parameters.get("value")
            )
            previous = build.current
            build.add(f"SELECT *\nFROM {previous}\nWHERE {predicate}")
        elif kind is TransformationKind.SORT:
            direction = "DESC" if parameters.get("direction") == "descending" else "ASC"
            nulls_first = parameters.get("nulls") == "first"
            if build.dialect is SqlDialect.POSTGRESQL:
                nulls = "NULLS FIRST" if nulls_first else "NULLS LAST"
                build.order_by = [f"{build.quote(name)} {direction} {nulls}" for name in inputs]
            else:
                null_rank = "0" if nulls_first else "1"
                value_rank = "1" if nulls_first else "0"
                build.order_by = [
                    f"CASE WHEN {build.quote(name)} IS NULL THEN {null_rank} ELSE {value_rank} END ASC, "
                    f"{build.quote(name)} {direction}"
                    for name in inputs
                ]
        elif kind is TransformationKind.DEDUPLICATE:
            keys = _string_list(parameters.get("keys", inputs))
            survivor = str(parameters.get("survivor", "first"))
            ordering = build.order_by or [f"{build.quote(name)} ASC" for name in keys]
            if survivor == "last":
                ordering = [
                    f"{item[:-4]} DESC" if item.endswith(" ASC") else f"{item[:-5]} ASC"
                    for item in ordering
                ]
            previous = build.current
            columns = ", ".join(build.quote(name) for name in build.columns)
            partition = ", ".join(build.quote(name) for name in keys)
            build.add(
                f"SELECT {columns}\nFROM (\n    SELECT {columns}, "
                f"ROW_NUMBER() OVER (PARTITION BY {partition} ORDER BY {', '.join(ordering)}) AS __pae_rank\n"
                f"    FROM {previous}\n) AS ranked\nWHERE __pae_rank = 1"
            )
        elif kind is TransformationKind.REPLACE:
            old = build.parameter(parameters.get("old"))
            new = build.parameter(parameters.get("new"))
            column = build.quote(inputs[0])
            self._replace_stage(
                build, inputs[0], f"CASE WHEN {column} = {old} THEN {new} ELSE {column} END"
            )
        elif kind is TransformationKind.HANDLE_NULL:
            self._replace_stage(
                build,
                inputs[0],
                f"COALESCE({build.quote(inputs[0])}, {build.parameter(parameters.get('value'))})",
            )
        elif kind is TransformationKind.DERIVE:
            if rule.output is None:
                raise InvalidSpecificationRule(f"Rule {rule.rule_id} requires output.")
            expression = self._derive(build, inputs, parameters)
            previous = build.current
            projection = ", ".join(build.quote(name) for name in build.columns)
            build.add(
                f"SELECT {projection}, {expression} AS {build.quote(rule.output)}\nFROM {previous}"
            )
            build.columns.append(rule.output)
        elif kind is TransformationKind.AGGREGATE:
            if rule.output is None:
                raise InvalidSpecificationRule(f"Rule {rule.rule_id} requires output.")
            groups = _string_list(parameters.get("group_by", []))
            function = str(parameters["function"]).upper()
            argument = (
                "*"
                if function == "COUNT" and parameters.get("count_all")
                else build.quote(inputs[0])
            )
            previous = build.current
            group_sql = ", ".join(build.quote(name) for name in groups)
            select = f"{group_sql}, " if group_sql else ""
            body = f"SELECT {select}{function}({argument}) AS {build.quote(rule.output)}\nFROM {previous}"
            if group_sql:
                body += f"\nGROUP BY {group_sql}"
            build.add(body)
            build.columns = [*groups, rule.output]
            build.order_by = []
        elif kind is TransformationKind.MASK:
            self._replace_stage(
                build,
                inputs[0],
                self._mask(build, inputs[0], str(parameters.get("strategy", "redact"))),
            )
        else:
            raise UnsupportedCapability(
                f"Transformation {kind.value} is unsupported by the SQL generator."
            )

    @staticmethod
    def _select_stage(build: _SqlBuild) -> None:
        previous = build.current
        columns = ", ".join(build.quote(name) for name in build.columns)
        build.add(f"SELECT {columns}\nFROM {previous}")

    @staticmethod
    def _replace_stage(build: _SqlBuild, field: str, expression: str) -> None:
        previous = build.current
        build.add(f"SELECT\n    {build.projection({field: expression})}\nFROM {previous}")

    @staticmethod
    def _filter(build: _SqlBuild, field: str, operator: str, value: Any) -> str:
        column = build.quote(field)
        if operator == "is_null":
            return f"{column} IS NULL"
        if operator == "not_null":
            return f"{column} IS NOT NULL"
        if operator == "in":
            values = value if isinstance(value, list) else []
            if not values:
                return "1 = 0"
            return f"{column} IN ({', '.join(build.parameter(item) for item in values)})"
        operations = {"eq": "=", "ne": "<>", "gt": ">", "gte": ">=", "lt": "<", "lte": "<="}
        if operator == "contains":
            return f"{column} LIKE {build.parameter('%' + str(value) + '%')}"
        if operator not in operations:
            raise InvalidSpecificationRule(f"Unsupported filter operator: {operator}")
        marker = build.parameter(value)
        return f"{column} {operations[operator]} {marker}"

    @staticmethod
    def _derive(build: _SqlBuild, inputs: list[str], parameters: dict[str, Any]) -> str:
        operation = str(parameters.get("operation"))
        columns = [build.quote(name) for name in inputs]
        if operation == "concat":
            separator = build.parameter(parameters.get("separator", ""))
            if build.dialect is SqlDialect.POSTGRESQL:
                return f"CONCAT_WS({separator}, {', '.join(columns)})"
            return f"CONCAT_WS({separator}, {', '.join(columns)})"
        if operation == "coalesce":
            values = [*columns, build.parameter(parameters.get("default"))]
            return f"COALESCE({', '.join(values)})"
        if len(columns) != 2 or operation not in {"add", "subtract", "multiply", "divide"}:
            raise InvalidSpecificationRule(f"Unsupported derive operation: {operation}")
        symbol = {"add": "+", "subtract": "-", "multiply": "*", "divide": "/"}[operation]
        return f"({columns[0]} {symbol} {columns[1]})"

    @staticmethod
    def _mask(build: _SqlBuild, field: str, strategy: str) -> str:
        column = build.quote(field)
        if strategy == "redact":
            return build.parameter("***")
        if strategy == "last4":
            text_type = {
                SqlDialect.POSTGRESQL: "TEXT",
                SqlDialect.MYSQL: "CHAR",
                SqlDialect.SQL_SERVER: "NVARCHAR(MAX)",
            }[build.dialect]
            return f"CONCAT({build.parameter('***')}, RIGHT(CAST({column} AS {text_type}), 4))"
        if strategy == "email":
            prefix = build.parameter("***@")
            if build.dialect is SqlDialect.POSTGRESQL:
                return f"CONCAT(LEFT({column}, 1), {prefix}, SPLIT_PART({column}, '@', 2))"
            if build.dialect is SqlDialect.MYSQL:
                return f"CONCAT(LEFT({column}, 1), {prefix}, SUBSTRING_INDEX({column}, '@', -1))"
            return f"CONCAT(LEFT({column}, 1), {prefix}, SUBSTRING({column}, CHARINDEX('@', {column}) + 1, LEN({column})))"
        if strategy == "hash":
            if build.dialect is SqlDialect.POSTGRESQL:
                return f"ENCODE(DIGEST(CAST({column} AS TEXT), 'sha256'), 'hex')"
            if build.dialect is SqlDialect.MYSQL:
                return f"SHA2(CAST({column} AS CHAR), 256)"
            return f"LOWER(CONVERT(VARCHAR(64), HASHBYTES('SHA2_256', CAST({column} AS NVARCHAR(MAX))), 2))"
        raise InvalidSpecificationRule(f"Unsupported masking strategy: {strategy}")

    def _validations(self, build: _SqlBuild, specification: PipelineSpecification) -> list[str]:
        statements: list[str] = []
        stage_sql = ",\n".join(build.stages)
        prefix = f"WITH\n{stage_sql}\n"
        for rule in specification.validations:
            column = build.quote(rule.field)
            parameters = rule.parameters
            if rule.kind is ValidationKind.NOT_NULL:
                invalid = f"{column} IS NULL"
            elif rule.kind is ValidationKind.UNIQUE:
                statements.append(
                    f"{prefix}SELECT {column}, COUNT(*) AS violation_count FROM {build.current} "
                    f"WHERE {column} IS NOT NULL GROUP BY {column} HAVING COUNT(*) > 1;"
                )
                continue
            elif rule.kind is ValidationKind.RANGE:
                parts = []
                if parameters.get("minimum") is not None:
                    parts.append(f"{column} < {build.parameter(parameters['minimum'])}")
                if parameters.get("maximum") is not None:
                    parts.append(f"{column} > {build.parameter(parameters['maximum'])}")
                invalid = " OR ".join(parts) or "1 = 0"
            elif rule.kind is ValidationKind.ALLOWED_VALUES:
                values = _string_list(parameters.get("values", []))
                markers = [build.parameter(value) for value in values]
                invalid = f"{column} NOT IN ({', '.join(markers)})" if markers else "1 = 1"
            elif rule.kind is ValidationKind.REGEX:
                marker = build.parameter(parameters["pattern"])
                if build.dialect is SqlDialect.POSTGRESQL:
                    invalid = f"NOT ({column} ~ {marker})"
                elif build.dialect is SqlDialect.MYSQL:
                    invalid = f"NOT ({column} REGEXP {marker})"
                else:
                    raise UnsupportedCapability(
                        "Regex validation is not portable to SQL Server and must be removed before generation."
                    )
            else:
                raise UnsupportedCapability(f"Validation {rule.kind.value} is unsupported.")
            statements.append(f"{prefix}SELECT * FROM {build.current} WHERE {invalid};")
        return statements

    @staticmethod
    def _validate_read_only(statement: str, dialect: SqlDialect) -> None:
        for parsed in sqlglot.parse(statement, read=_READ_DIALECT[dialect]):
            if parsed is None:
                raise InvalidSpecificationRule("Generated SQL contained an empty statement.")
            if parsed.key not in {"select", "union", "with"}:
                raise InvalidSpecificationRule("Generated SQL must contain only read-only SELECTs.")

    @staticmethod
    def _readme(specification: PipelineSpecification, dialect: SqlDialect) -> str:
        source = specification.sources[0]
        assert isinstance(source, DatabaseSource)
        return (
            f"# {specification.name} ({dialect.value})\n\n"
            "This package is a read-only SQL result contract. It does not write to source or destination tables.\n"
            f"Resolve database connection `{source.connection_ref}` outside this package, bind values from "
            "`parameters.json`, execute `pipeline.sql`, then run `validation_queries.sql`.\n"
            "File sources and multi-source Join are outside the SQL MVP boundary.\n"
        )
