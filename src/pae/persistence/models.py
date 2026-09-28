"""Persistence-facing records and authorization roles."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum, StrEnum


class Role(StrEnum):
    OWNER = "owner"
    EDITOR = "editor"
    VIEWER = "viewer"


class Permission(IntEnum):
    VIEW = 1
    EDIT = 2
    ADMINISTER = 3


ROLE_PERMISSION = {
    Role.VIEWER: Permission.VIEW,
    Role.EDITOR: Permission.EDIT,
    Role.OWNER: Permission.ADMINISTER,
}


@dataclass(frozen=True)
class Principal:
    user_id: str
    display_name: str


@dataclass(frozen=True)
class ProjectView:
    project_id: str
    owner_id: str
    name: str
    status: str
    current_revision: int
    record_version: int
    specification_confirmed: bool
    created_by: str
    updated_by: str
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class JobView:
    job_id: str
    project_id: str
    revision: int
    operation: str
    status: str
    progress_percentage: int
    attempt: int
    max_attempts: int
    cancellation_requested: bool
    error_code: str | None
