"""Secret resolution that keeps credential material outside persisted source configuration."""

from __future__ import annotations

import os
import re
from typing import Protocol

from pydantic import SecretStr

from pae.connectors.models import DatabaseCredential
from pae.persistence.errors import SecretReferenceUnavailable


class SecretResolver(Protocol):
    def resolve(self, reference: str) -> DatabaseCredential: ...


class EnvironmentSecretResolver:
    """Resolve ``secret://name`` from ``PAE_SECRET_NAME`` at connection time."""

    def resolve(self, reference: str) -> DatabaseCredential:
        if not reference.startswith("secret://"):
            raise SecretReferenceUnavailable("The database secret reference is invalid.")
        name = reference.removeprefix("secret://")
        variable = "PAE_SECRET_" + re.sub(r"[^A-Za-z0-9]", "_", name).upper()
        value = os.environ.get(variable)
        if not value:
            raise SecretReferenceUnavailable(
                "The database credential is unavailable.",
                details={"secret_reference": reference, "guidance": f"Configure {variable}."},
            )
        return DatabaseCredential(password=SecretStr(value))
