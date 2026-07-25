<#
.SYNOPSIS
  Batch 2b: wire the new modules into the search engine. MEASURED.
.DESCRIPTION
  Replaces three files and re-runs the backfill with OCR correction:
    packages/search/ranking.py   raw score sum  ->  RRF
    packages/search/fts.py       text column    ->  text_normalized (index now used)
    packages/search/fuzzy.py     similarity()   ->  % operator (GIN index now used)
    scripts/backfill_normalized_text.py  adds OCR correction

  Requires _eval/baseline.json to exist. Compares after wiring and
  reports whether quality improved or regressed.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipBackfill,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch3"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch3 folder not found: $PatchDir" }

$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

Write-Step "0/5  Baseline gate"
if (-not (Test-Path $Baseline)) {
    Write-Err2 "No baseline at $Baseline"
    Write-Warn2 "Run .\tools\11-baseline.ps1 first. Without a baseline there is"
    Write-Warn2 "no way to prove this change helped."
    exit 1
}
Write-Ok "baseline found: $Baseline"

Write-Step "1/5  Replace search modules"
$files = @(
  @{ p = "packages\search\ranking.py"; n = "RRF instead of raw score sum" },
  @{ p = "packages\search\fts.py";     n = "read text_normalized (matches the index)" },
  @{ p = "packages\search\fuzzy.py";   n = "% operator so the GIN index is used" },
  @{ p = "scripts\backfill_normalized_text.py"; n = "adds OCR correction" }
)
$bkDir = Join-Path "_backup" ("wire-" + (Get-Stamp))
foreach ($f in $files) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Err2 ("missing: " + $f.p); continue }
    if ($DryRun) { Write-Dry ($f.p + "  - " + $f.n); continue }
    if (Test-Path -LiteralPath $f.p) {
        $bk = Join-Path $bkDir $f.p
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $f.p -Destination $bk -Force
    }
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $f.p -Content $c
    Write-Ok ($f.p + "  - " + $f.n)
}
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "2/5  Syntax check"
if ($DryRun) { Write-Dry "would run py_compile" }
else {
    foreach ($f in $files) {
        & $py.Source -m py_compile $f.p 2>&1 | Out-Null
        if ($LASTEXITCODE -eq 0) { Write-Ok ("syntax ok: " + $f.p) }
        else { Write-Err2 ("SYNTAX ERROR: " + $f.p); Write-Warn2 "revert: copy back from $bkDir"; exit 1 }
    }
}

Write-Step "3/5  Re-run backfill with OCR correction"
if ($DryRun) { Write-Dry "would run backfill --force" }
elseif ($SkipBackfill) { Write-Warn2 "skipped (-SkipBackfill). Stretched OCR text stays in the index." }
else {
    Write-Info "this rewrites text_normalized only; text_raw is never touched"
    & $py.Source "scripts/backfill_normalized_text.py" --force
    if ($LASTEXITCODE -ne 0) { Write-Err2 "backfill failed"; exit 1 }
    Write-Ok "backfill complete"
}

Write-Step "4/5  Re-run existing tests"
if (-not $DryRun) {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "unit tests still pass" }
    else { Write-Warn2 "some unit tests failed - review before trusting the numbers" }
}

Write-Step "5/5  Measure against baseline"
if ($DryRun) { Write-Dry "would compare against $Baseline"; exit 0 }
& $py.Source "scripts/eval_search.py" --compare $Baseline
$evalCode = $LASTEXITCODE

Write-Host ""
if ($evalCode -eq 0) {
    Write-Ok "No regression detected."
    Write-Host "  Commit:  git add -A ; git commit -m 'fix: batch 2b - RRF, indexed search, OCR correction'" -ForegroundColor Gray
} else {
    Write-Err2 "Regression detected. Do NOT commit."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
    Write-Host "  Then send me the comparison output." -ForegroundColor Yellow
}
Write-Host ""
exit $evalCode
