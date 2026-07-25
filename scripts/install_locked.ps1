$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

python -m pip install --upgrade pip setuptools wheel

$lock = "requirements\requirements.lock.txt"
if (-not (Test-Path $lock)) {
    throw "Missing $lock. Run the freeze script first."
}

python -m pip install -r $lock

Write-Host ""
Write-Host "========================================"
Write-Host "Locked environment installed successfully"
Write-Host "========================================"
