"""Task definition model — represents a single provisioning task from JSON."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from app.models.enums import TaskType


class DetectRule(BaseModel):
    """Rule to check if a task's target state is already satisfied."""

    type: str
    value: str


class TaskDefinition(BaseModel):
    """
    A single task in a provisioning profile.

    Loaded from profile JSON. This is the *declaration* of what to do,
    not the runtime execution record (that's in SQLite).
    """

    id: str
    name: str
    type: TaskType
    order: int = 0

    # Source — one of these will be set depending on type
    path: str | None = None
    command: str | None = None
    package_ref: str | None = None
    winget_id: str | None = None

    arguments: dict[str, Any] = Field(default_factory=dict)
    timeout: int = 300
    retry_count: int = 0
    detect_rule: DetectRule | None = None
    requires_admin: bool = False
    continue_on_error: bool = False
    enabled: bool = True

    def resolve_arguments(self, context: dict[str, str]) -> dict[str, Any]:
        """Replace {{placeholder}} values in arguments with context values."""
        resolved = {}
        for key, value in self.arguments.items():
            if isinstance(value, str) and value.startswith("{{") and value.endswith("}}"):
                placeholder = value[2:-2]
                resolved[key] = context.get(placeholder, value)
            else:
                resolved[key] = value
        return resolved
