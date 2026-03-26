# Collect device inventory and output as JSON
# This is the standalone .ps1 version of the inline script in inventory.py
# Can be used independently or referenced by profiles
$ErrorActionPreference = 'SilentlyContinue'

$cs = Get-CimInstance Win32_ComputerSystem
$bios = Get-CimInstance Win32_BIOS
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1
$os = Get-CimInstance Win32_OperatingSystem
$gpu = Get-CimInstance Win32_VideoController | Select-Object -First 1

$disks = @(Get-CimInstance Win32_DiskDrive | ForEach-Object {
    @{
        model   = $_.Model
        size_gb = [math]::Round($_.Size / 1GB, 1)
        type    = if ($_.MediaType -match 'SSD|Solid') { 'SSD' } else { 'HDD' }
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
