$ErrorActionPreference = "Stop"

function Backup-File {
    param([Parameter(Mandatory = $true)][string]$Path)
    if (Test-Path $Path) {
        Copy-Item $Path "$Path.bak" -Force
    }
}

function Write-Utf8File {
    param(
        [Parameter(Mandatory = $true)][string]$Path,
        [Parameter(Mandatory = $true)][string]$Content
    )
    $dir = Split-Path $Path -Parent
    if ($dir -and -not (Test-Path $dir)) {
        New-Item -ItemType Directory -Force -Path $dir | Out-Null
    }
    Set-Content -Path $Path -Value $Content -Encoding UTF8
}

Write-Host "This pack is shipped as files inside the zip." -ForegroundColor Cyan
Write-Host "Copy the files into your project root, or use this zip as a reference." -ForegroundColor Cyan
