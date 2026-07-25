$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

python -m pip install --upgrade pip setuptools wheel

$bundles = @(
    "requirements\00-core.txt",
    "requirements\01-import.txt",
    "requirements\02-ocr.txt",
    "requirements\03-search.txt",
    "requirements\04-graph.txt",
    "requirements\05-rag.txt",
    "requirements\06-api.txt",
    "requirements\07-dev.txt"
)

foreach ($bundle in $bundles) {
    Write-Host ""
    Write-Host "========================================"
    Write-Host "Installing $bundle"
    Write-Host "========================================"
    python -m pip install -r $bundle
}

Write-Host ""
Write-Host "========================================"
Write-Host "All requirement bundles installed"
Write-Host "========================================"
