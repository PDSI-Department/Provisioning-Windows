"""Profile definition model — a provisioning profile loaded from JSON."""

from __future__ import annotations

from pydantic import BaseModel

from app.models.task_definition import TaskDefinition


class ProfileDefinition(BaseModel):
    """
    A provisioning profile defining which tasks to run for a device category.
    Loaded from profile JSON files (bundled or from SSD kit).
    """

    profile_id: str
    name: str
    description: str = ""
    icon: str = "computer"
    version: str = "1.0.0"
    author: str = ""
    tasks: list[TaskDefinition] = []

    def get_enabled_tasks(self) -> list[TaskDefinition]:
        """Return tasks that are enabled, sorted by order."""
        return sorted(
            [t for t in self.tasks if t.enabled],
            key=lambda t: t.order,
        )
