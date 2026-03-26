param(
    [string]$Hostname
)

$ErrorActionPreference = 'Stop'

try {
    if ([string]::IsNullOrWhiteSpace($Hostname)) {
        Write-Output "Hostname is empty - skipping rename"
        exit 0
    }

    $current = $env:COMPUTERNAME
    if ($current -eq $Hostname) {
        Write-Output "Hostname already set to $Hostname - skipping"
        exit 0
    }

    Write-Output "Renaming computer from '$current' to '$Hostname'"
    Rename-Computer -NewName $Hostname -Force

    Write-Output "Hostname renamed to $Hostname (reboot required to take effect)"
    exit 0
}
catch {
    Write-Error "Failed to rename hostname: $_"
    exit 1
}
