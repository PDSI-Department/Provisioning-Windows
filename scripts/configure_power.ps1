# Configure power settings for office desktop usage
$ErrorActionPreference = 'SilentlyContinue'

Write-Output "Configuring power settings..."

# Set to High Performance plan
$highPerf = powercfg /list | Select-String "High performance"
if ($highPerf -match '([a-f0-9-]{36})') {
    powercfg /setactive $Matches[1]
    Write-Output "Activated High Performance power plan"
} else {
    Write-Output "High Performance plan not found, using current plan"
}

# Disable sleep and hibernate on AC
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 30

# Disable USB selective suspend
powercfg /setacvalueindex SCHEME_CURRENT 2a737441-1930-4402-8d77-b2bebba308a3 48e6b7a6-50f5-4782-a5d4-53bb8f07e226 0

Write-Output "Power settings configured"
exit 0
