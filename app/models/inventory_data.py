"""Inventory data model — hardware and software info collected from device."""

from __future__ import annotations

from pydantic import BaseModel


class InventoryData(BaseModel):
    """Hardware and software inventory snapshot."""

    manufacturer: str = ""
    model: str = ""
    serial_number: str = ""
    cpu: str = ""
    ram_gb: float = 0.0
    storage: list[dict] = []
    gpu: str = ""
    os_name: str = ""
    os_version: str = ""
    os_build: str = ""
    hostname: str = ""
    ip_addresses: list[str] = []
    mac_addresses: list[str] = []
    installed_software: list[dict] = []
    collected_at: str = ""
