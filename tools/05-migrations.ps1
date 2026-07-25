<#
.SYNOPSIS
  Install (and optionally apply) the migration that fixes the search indexes.
#>
[CmdletBinding()]
param([switch]$Apply, [switch]$SkipBackfill, [int]$BatchSize = 1000,
      [string]$PatchDir = "$PSScriptRoot\..\patch")
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

$migFile = "a1b2c3d4e5f6_split_raw_normalized_and_fix_indexes.py"
$src = Join-Path $PatchDir ("alembic\versions\" + $migFile)
$dst = "alembic\versions\" + $migFile

Write-Step "1/4  Install migration file"
if (-not (Test-Path -LiteralPath $src)) { throw "migration file missing: $src" }
if (Test-Path -LiteralPath $dst) { Write-Info "already installed" }
else {
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $dst -Content $c
    Write-Ok "installed: $dst"
}

Write-Step "2/4  Verify migration chain"
$py = Get-Python
if ($py) {
    & $py.Source -m py_compile $dst 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "migration file syntax ok" }
    else { Write-Err2 "syntax error in migration file - stopping"; exit 1 }
}
Write-Info "new revision a1b2c3d4e5f6 branches from 08af36dbc5dc"

Write-Step "3/4  Apply migration"
if (-not $Apply) {
    Write-Warn2 "NOT applied (no -Apply flag)."
    Write-Host ""
    Write-Host "  What it will do:" -ForegroundColor Gray
    Write-Host "    + columns: text_raw, text_normalized, canonicalizer_version," -ForegroundColor Gray
    Write-Host "               ocr_confidence, layout_confidence" -ForegroundColor Gray
    Write-Host "    + copy text -> text_raw (preserve the original)" -ForegroundColor Gray
    Write-Host "    - drop old unused index ix_page_elements_text_fts" -ForegroundColor Gray
    Write-Host "    + GIN FTS index on text_normalized" -ForegroundColor Gray
    Write-Host "    + GIN trigram index on text_normalized" -ForegroundColor Gray
    Write-Host "    + composite index (page_id, element_order)" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  To apply:  .\tools\05-migrations.ps1 -Apply" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

$hasBackup = (Test-Path "_backup") -and
             ((Get-ChildItem "_backup" -Recurse -Filter "*.dump" -ErrorAction SilentlyContinue).Count -gt 0)
if (-not $hasBackup) {
    Write-Warn2 "No pg_dump found under _backup/"
    $ans = Read-Host "Continue anyway? type yes"
    if ($ans -ne "yes") { Write-Info "cancelled"; exit 0 }
}

Write-Info "running: alembic upgrade head"
& $py.Source -m alembic upgrade head
if ($LASTEXITCODE -ne 0) { Write-Err2 "migration failed. Revert with: alembic downgrade -1"; exit 1 }
Write-Ok "migration applied"

Write-Step "4/4  Backfill text_normalized"
if ($SkipBackfill) {
    Write-Warn2 "skipped. Search will not work until you run:"
    Write-Host "    python scripts/backfill_normalized_text.py" -ForegroundColor Yellow
    exit 0
}
if (-not (Test-Path "scripts\backfill_normalized_text.py")) {
    Write-Err2 "backfill script not installed. Run 04-install-canonicalizer.ps1 first."
    exit 1
}
if ($py) {
    & $py.Source "scripts/backfill_normalized_text.py" --batch-size $BatchSize
    if ($LASTEXITCODE -eq 0) { Write-Ok "backfill complete" }
    else { Write-Err2 "backfill failed - original text in text_raw is intact" }
} else { Write-Warn2 "python not found - run the backfill manually" }

Write-Host ""
Write-Warn2 "NOTE: fts.py and fuzzy.py still read the old 'text' column."
Write-Warn2 "The new indexes are not used yet. No speed gain until batch 2."
Write-Host ""
