<#
.SYNOPSIS
  Run the IslamicAI fix batch in the correct order.
.EXAMPLE
  .\tools\RUN-ALL.ps1 -DryRun
  .\tools\RUN-ALL.ps1
  .\tools\RUN-ALL.ps1 -ApplyMigrations
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$ApplyMigrations, [switch]$SkipBackup, [switch]$DeleteBakFiles)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

Write-Host ""
Write-Host "  ==========================================================" -ForegroundColor Cyan
Write-Host "    IslamicAI - fix batch 1" -ForegroundColor Cyan
Write-Host "    secrets leak / 79MB derived data / 3 destructive paths" -ForegroundColor Cyan
Write-Host "    / incomplete Arabic canonicalizer" -ForegroundColor Cyan
Write-Host "  ==========================================================" -ForegroundColor Cyan
Write-Host ""

if ($DryRun) { Write-Host "  DRY RUN: nothing will be written." -ForegroundColor Magenta; Write-Host "" }
else {
    Write-Host "  This will modify your repository. Make sure you have:" -ForegroundColor Yellow
    Write-Host "    - committed your current work (git commit)" -ForegroundColor Yellow
    Write-Host ("    - the right folder: " + (Get-Location).Path) -ForegroundColor Yellow
    Write-Host ""
    $ans = Read-Host "  Type yes to continue"
    if ($ans -ne "yes") { Write-Host "  Cancelled."; exit 0 }
}

$done = @(); $failed = @()
function Invoke-Step {
    param($Number, $Name, $Script, $ArgsHash)
    Write-Host ""
    Write-Host ("  " + ("-" * 56)) -ForegroundColor DarkGray
    Write-Host "   Step $Number - $Name" -ForegroundColor White
    Write-Host ("  " + ("-" * 56)) -ForegroundColor DarkGray
    try   { & (Join-Path $PSScriptRoot $Script) @ArgsHash; $script:done += "$Number $Name" }
    catch { Write-Err2 ("step " + $Number + " failed: " + $_); $script:failed += "$Number $Name" }
}

if (-not $SkipBackup -and -not $DryRun) { Invoke-Step "00" "Backup" "00-backup.ps1" @{} }
else { Write-Warn2 "skipping backup" }

Invoke-Step "01" "Rotate secrets"  "01-secrets.ps1"    @{ DryRun = $DryRun }
Invoke-Step "02" "Clean repo"      "02-purge.ps1"      @{ DryRun = $DryRun; DeleteBakFiles = $DeleteBakFiles }
Invoke-Step "03" "Guardrails"      "03-guardrails.ps1" @{ DryRun = $DryRun }
Invoke-Step "04" "Canonicalizer"   "04-install-canonicalizer.ps1" @{ DryRun = $DryRun }

if (-not $DryRun) { Invoke-Step "05" "Migration" "05-migrations.ps1" @{ Apply = $ApplyMigrations } }
else { Write-Dry "step 05 skipped in dry run" }

if (-not $DryRun) { Invoke-Step "06" "Verify" "06-verify.ps1" @{} }

Write-Host ""
Write-Host ("  " + ("=" * 56)) -ForegroundColor Cyan
Write-Host "   Summary" -ForegroundColor Cyan
Write-Host ("  " + ("=" * 56)) -ForegroundColor Cyan
foreach ($s in $done)   { Write-Host "    DONE   $s" -ForegroundColor Green }
foreach ($s in $failed) { Write-Host "    FAILED $s" -ForegroundColor Red }
Write-Host ""
if (-not $DryRun) {
    Write-Host "  Review before committing:" -ForegroundColor Yellow
    Write-Host "    git status" -ForegroundColor Gray
    Write-Host "    git diff" -ForegroundColor Gray
    Write-Host "    git add -A ; git commit -m 'fix: batch 1'" -ForegroundColor Gray
    Write-Host ""
    if (-not $ApplyMigrations) {
        Write-Host "  Migration not applied. When ready:" -ForegroundColor Yellow
        Write-Host "    .\tools\05-migrations.ps1 -Apply" -ForegroundColor Gray
        Write-Host ""
    }
}
