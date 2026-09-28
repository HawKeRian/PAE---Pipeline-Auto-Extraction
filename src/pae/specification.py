"""Build a confirmed Pipeline Specification from user-edited, validated proposal rules."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import Field, model_validator

from pae.ai.models import TransformationDraft, ValidationDraft
from pae.domain.capabilities import MVP_CAPABILITIES
from pae.domain.enums import TransformationKind
from pae.domain.models import (
    DatabaseSource,
    FieldDefinition,
    FileDiscoveryContract,
    FileSource,
    OutputContract,
    PipelineSpecification,
    StrictModel,
    TargetRuntime,
    TransformationRule,
    ValidationRule,
)
from pae.persistence.errors import InvalidSpecificationRule, UnsupportedCapability
from pae.profiling.models import ConfirmedSchema


class SpecificationConfirmationRequest(StrictModel):
    proposal_id: str = Field(min_length=1)
    name: str = Field(min_length=1, max_length=120)
    transformations: tuple[TransformationDraft, ...]
    validations: tuple[ValidationDraft, ...] = ()
    output: OutputContract
    target: TargetRuntime
    assumptions_acknowledged: bool = False

    @model_validator(mode="after")
    def order_is_consecutive(self) -> SpecificationConfirmationRequest:
        orders = [rule.order for rule in self.transformations]
        if orders and sorted(orders) != list(range(1, len(orders) + 1)):
            raise ValueError("transformation order values must be consecutive starting at 1")
        rule_ids = [rule.rule_id for rule in self.transformations]
        rule_ids.extend(rule.rule_id for rule in self.validations)
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_id values must be unique")
        return self


def validate_capability(request: SpecificationConfirmationRequest) -> None:
    if any(rule.kind is TransformationKind.JOIN for rule in request.transformations):
        raise UnsupportedCapability(
            "Multi-source Join is deferred after MVP. Remove the Join rule to continue.",
            details={"capability": "join", "scope": "deferred"},
        )
    capability = next(
        (
            item
            for item in MVP_CAPABILITIES
            if item.language is request.target.language
            and item.dialect is request.target.sql_dialect
        ),
        None,
    )
    if capability is None or request.output.format not in capability.outputs:
        raise UnsupportedCapability(
            "The selected output is not supported by the target language and SQL dialect."
        )
    unsupported = {rule.kind for rule in request.transformations} - capability.transformations
    if unsupported:
        raise UnsupportedCapability(
            "One or more transformation rules are unsupported by the selected target.",
            details={"unsupported": sorted(item.value for item in unsupported)},
        )


def build_specification(
    project_id: str,
    source: dict[str, Any],
    schema: ConfirmedSchema,
    request: SpecificationConfirmationRequest,
    actor_id: str,
) -> PipelineSpecification:
    validate_capability(request)
    selected = {field.name for field in schema.fields if field.selected}
    unknown = {
        name for rule in request.transformations for name in rule.inputs if name not in selected
    }
    unknown.update(rule.field for rule in request.validations if rule.field not in selected)
    if unknown:
        raise InvalidSpecificationRule(
            "Rules reference fields outside the confirmed schema.",
            details={"unknown_fields": sorted(unknown)},
        )
    source_id = "input"
    config = source["config"]
    if source["kind"] == "file":
        runtime_config = config["runtime"]
        runtime = FileDiscoveryContract(
            filename_pattern=runtime_config["filename_pattern"],
            recursive=bool(runtime_config["recursive"]),
            schema_policy=runtime_config["schema_policy"],
        )
        source_model: FileSource | DatabaseSource = FileSource(
            source_id=source_id,
            file_format=config["file_format"],
            original_name=config["original_name"],
            sheet_name=config.get("sheet_name"),
            delimiter=config.get("delimiter"),
            encoding=config.get("encoding") or "utf-8",
            sample_limit=int(config.get("profile", {}).get("sampled_rows", 10_000)),
            runtime=runtime,
        )
    else:
        source_model = DatabaseSource(
            source_id=source_id,
            database_type=config["database_type"],
            connection_ref=config["connection_ref"],
            schema_name=config.get("schema_name"),
            object_name=config.get("object_name"),
            read_only_query=config.get("read_only_query"),
            sample_limit=int(config.get("sample_limit", 10_000)),
        )
    fields = tuple(
        FieldDefinition(
            source_id=source_id,
            source_name=field.name,
            target_name=field.name,
            inferred_type=field.inferred_type,
            confirmed_type=field.confirmed_type,
            nullable=field.nullable,
            required=field.required,
            selected=field.selected,
            confidence=field.confidence,
            null_percentage=field.null_percentage,
            distinct_count=field.distinct_count,
            pii_classification=field.pii_classification,
            samples_masked=field.samples_masked,
        )
        for field in schema.fields
    )
    transformations = tuple(
        TransformationRule(
            rule_id=rule.rule_id,
            order=rule.order,
            kind=rule.kind,
            inputs=rule.inputs,
            output=rule.output,
            parameters=rule.parameters,
        )
        for rule in request.transformations
    )
    validations = tuple(
        ValidationRule(
            rule_id=rule.rule_id,
            field=rule.field,
            kind=rule.kind,
            severity=rule.severity,
            parameters=rule.parameters,
        )
        for rule in request.validations
    )
    encoded_source = json.dumps(source, sort_keys=True, separators=(",", ":"))
    source_fingerprint = hashlib.sha256(encoded_source.encode("utf-8")).hexdigest()
    return PipelineSpecification(
        specification_id=uuid4(),
        project_id=UUID(project_id),
        revision=schema.revision,
        name=request.name,
        source_fingerprint=source_fingerprint,
        sources=(source_model,),
        fields=fields,
        transformations=transformations,
        validations=validations,
        output=request.output,
        target=request.target,
        confirmed_by=actor_id,
        confirmed_at=datetime.now(UTC),
    )
