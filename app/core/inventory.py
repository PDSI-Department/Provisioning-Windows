"""
Inventory collection module.

Collects hardware and software information from the device
using PowerShell (WMI/CIM queries) and returns structured data.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from app.core.powershell_runner import PowerShellRunner
from app.models.inventory_data import InventoryData

logger = logging.getLogger(__name__)

# PowerShell script that collects everything and outputs JSON
INVENTORY_PS_SCRIPT = r"""
$ErrorActionPreference = 'SilentlyContinue'

$cs = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem
$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1

$disks = @(Get-CimInstance Win32_DiskDrive | ForEach-Object {
    @{
        model    = $_.Model
        size_gb  = [math]::Round($_.Size / 1GB, 1)
        type     = if ($_.MediaType -match 'SSD|Solid') { 'SSD' } else { 'HDD' }
    }
})

$nics = @(Get-CimInstance Win32_NetworkAdapterConfiguration | Where-Object { $_.IPEnabled } | ForEach-Object {
    @{
        ip  = @($_.IPAddress | Where-Object { $_ -match '^\d+\.\d+\.\d+\.\d+$' })
        mac = $_.MACAddress
    }
})

$software = @(Get-ItemProperty HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*,
    HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\* -ErrorAction SilentlyContinue |
    Where-Object { $_.DisplayName } |
    Select-Object DisplayName, DisplayVersion, Publisher |
    Sort-Object DisplayName -Unique |
    ForEach-Object {
        @{
            name      = $_.DisplayName
            version   = $_.DisplayVersion
            publisher = $_.Publisher
        }
    }
)

$result = @{
    manufacturer       = $cs.Manufacturer
    model              = $cs.Model
    serial_number      = $bios.SerialNumber
    cpu                = $cpu.Name
    ram_gb             = [math]::Round($cs.TotalPhysicalMemory / 1GB, 1)
    storage            = $disks
    gpu                = $gpu.Name
    os_name            = $os.Caption
    os_version         = $os.Version
    os_build           = $os.BuildNumber
    hostname           = $env:COMPUTERNAME
    ip_addresses       = @($nics | ForEach-Object { $_.ip } | Where-Object { $_ })
    mac_addresses      = @($nics | ForEach-Object { $_.mac } | Where-Object { $_ })
    installed_software = $software
}

$result | ConvertTo-Json -Depth 5 -Compress
"""


class InventoryCollector:
    """Collects device hardware and software inventory."""

    def __init__(self, ps_runner: PowerShellRunner | None = None):
        self.ps_runner = ps_runner or PowerShellRunner()

    def collect(self, timeout: int = 120) -> InventoryData:
        """
        Run the inventory PowerShell script and parse results.
        Returns an InventoryData model even on partial failure.
        """
        logger.info("Starting inventory collection")

        result = self.ps_runner.run_command(INVENTORY_PS_SCRIPT, timeout=timeout)

        if not result.success:
            logger.error("Inventory PS failed: %s", result.error_message)
            return InventoryData(
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        try:
            raw = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse inventory JSON: %s", exc)
            logger.debug("Raw stdout: %s", result.stdout[:500])
            return InventoryData(
                collected_at=datetime.now(timezone.utc).isoformat(),
            )

        inventory = InventoryData(
            manufacturer=raw.get("manufacturer", ""),
            model=raw.get("model", ""),
            serial_number=raw.get("serial_number", ""),
            cpu=raw.get("cpu", ""),
            ram_gb=raw.get("ram_gb", 0),
            storage=raw.get("storage", []),
            gpu=raw.get("gpu", ""),
            os_name=raw.get("os_name", ""),
            os_version=raw.get("os_version", ""),
            os_build=raw.get("os_build", ""),
            hostname=raw.get("hostname", ""),
            ip_addresses=raw.get("ip_addresses", []),
            mac_addresses=raw.get("mac_addresses", []),
            installed_software=raw.get("installed_software", []),
            collected_at=datetime.now(timezone.utc).isoformat(),
        )

        logger.info(
            "Inventory collected: %s %s (S/N: %s)",
            inventory.manufacturer,
            inventory.model,
            inventory.serial_number,
        )
        return inventory
