"""Device metadata model — user input about the device being provisioned."""

from __future__ import annotations

from pydantic import BaseModel, Field


class DeviceMetadata(BaseModel):
    """
    Information about the device being provisioned.
    Filled in by IT Support before starting provisioning.
    """

    asset_tag: str = ""
    user_name: str = ""
    department: str = ""
    location: str = ""
    hostname: str = ""
    notes: str = ""

    def to_context(self) -> dict[str, str]:
        """Convert to a context dict for template variable resolution."""
        return {
            "asset_tag": self.asset_tag,
            "user_name": self.user_name,
            "department": self.department,
            "location": self.location,
            "hostname": self.hostname,
            "notes": self.notes,
        }
