# Ensure winget is available and functional
$ErrorActionPreference = 'Stop'

Write-Output "Checking winget availability..."

try {
    $wingetPath = Get-Command winget -ErrorAction Stop
    $version = winget --version
    Write-Output "winget found: $version at $($wingetPath.Source)"

    # Accept source agreements
    winget source update --accept-source-agreements | Out-Null
    Write-Output "winget source updated"

    exit 0
}
catch {
    Write-Output "winget not found, attempting to install..."

    # Try to install via Add-AppxPackage (Windows 10/11)
    try {
        $progressPreference = 'SilentlyContinue'
        $releases = Invoke-RestMethod -Uri "https://api.github.com/repos/microsoft/winget-cli/releases/latest"
        $msixUrl = $releases.assets | Where-Object { $_.name -match '\.msixbundle$' } | Select-Object -First 1 -ExpandProperty browser_download_url

        $outPath = "$env:TEMP\winget.msixbundle"
        Invoke-WebRequest -Uri $msixUrl -OutFile $outPath
        Add-AppxPackage -Path $outPath

        Write-Output "winget installed successfully"
        exit 0
    }
    catch {
        Write-Error "Failed to install winget: $_"
        exit 1
    }
}
