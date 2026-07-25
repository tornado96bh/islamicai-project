<#
.SYNOPSIS
  Capture a baseline measurement of current search quality.
.DESCRIPTION
  This must run BEFORE any behaviour change. Without a baseline there is
  no way to prove a change helped - which is exactly how the ranking
  regression went unnoticed.
  Writes _eval/baseline.json.
#>
[CmdletBinding()]
param([string]$Out = "_eval\baseline.json", [int]$K = 10, [int]$Limit = 20)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

if (-not (Test-Path "scripts\eval_search.py")) {
    Write-Err2 "eval harness not installed. Run 10-install-batch2.ps1 first."
    exit 1
}

Write-Step "Checking database connectivity"
$docker = Get-Command docker -ErrorAction SilentlyContinue
if ($docker) {
    $running = docker ps --filter "name=islamicai_postgres" --format "{{.Names}}" 2>$null
    if ([string]::IsNullOrWhiteSpace($running)) {
        Write-Warn2 "postgres container is not running. Start it first:"
        Write-Host "    docker compose up -d postgres" -ForegroundColor Gray
        exit 1
    }
    Write-Ok "postgres container is running"
}

Write-Step "Running evaluation"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $Out) | Out-Null
& $py.Source "scripts/eval_search.py" --k $K --limit $Limit --save $Out

if ($LASTEXITCODE -ne 0) {
    Write-Err2 "evaluation failed"
    Write-Warn2 "check that .env password matches the database"
    exit 1
}

Write-Ok "baseline saved: $Out"
Write-Host ""
Write-Host "  Keep this file. After any change, run:" -ForegroundColor Cyan
Write-Host "    python scripts/eval_search.py --compare $Out" -ForegroundColor Gray
Write-Host ""
Write-Host "  Send these numbers back before wiring anything." -ForegroundColor Yellow
Write-Host ""
