"""MVP generator capability declarations used for fail-fast validation."""

from pae.domain.enums import OutputFormat, SqlDialect, TargetLanguage, TransformationKind
from pae.domain.interfaces import GeneratorCapabilities

COMMON_TRANSFORMATIONS = frozenset(
    {
        TransformationKind.INCLUDE,
        TransformationKind.EXCLUDE,
        TransformationKind.RENAME,
        TransformationKind.CAST,
        TransformationKind.FILTER,
        TransformationKind.SORT,
        TransformationKind.DEDUPLICATE,
        TransformationKind.REPLACE,
        TransformationKind.HANDLE_NULL,
        TransformationKind.DERIVE,
        TransformationKind.AGGREGATE,
        TransformationKind.MASK,
    }
)

PYTHON_CAPABILITIES = GeneratorCapabilities(
    language=TargetLanguage.PYTHON,
    dialect=None,
    transformations=COMMON_TRANSFORMATIONS,
    outputs=frozenset({OutputFormat.CSV, OutputFormat.JSON_LINES, OutputFormat.PARQUET}),
)

SQL_CAPABILITIES = tuple(
    GeneratorCapabilities(
        language=TargetLanguage.SQL,
        dialect=dialect,
        transformations=COMMON_TRANSFORMATIONS,
        outputs=frozenset({OutputFormat.SQL_RESULT}),
    )
    for dialect in SqlDialect
)

JAVASCRIPT_CAPABILITIES = GeneratorCapabilities(
    language=TargetLanguage.JAVASCRIPT,
    dialect=None,
    transformations=COMMON_TRANSFORMATIONS,
    outputs=frozenset({OutputFormat.CSV, OutputFormat.JSON_LINES}),
)

MVP_CAPABILITIES = (PYTHON_CAPABILITIES, *SQL_CAPABILITIES, JAVASCRIPT_CAPABILITIES)
