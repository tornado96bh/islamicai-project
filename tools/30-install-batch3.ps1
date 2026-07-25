<#
.SYNOPSIS
  Batch 3: fix the score-scale incoherence, complete the contracts, clean the index.
.DESCRIPTION
  The measurement exposed a system-level bug: ranking.py produces RRF scores
  around 0.016 but reranker.py adds about 1.235 on top, so the visible ranking
  was decided by the fake 256-dim hash embedding, not by RRF. And filters.py
  compares against absolute thresholds (0.15 / 1.25 / 1.55) calibrated for the
  old score scale - results only survived by accident.

  This batch:
    packages/search/reranker.py   scale-aware, embedding weight 0, explains itself
    packages/search/filters.py    relative thresholds instead of magic numbers
    packages/schemas/             complete contracts, single source of truth
    scripts/clean_index_quality.py  excludes blank / noise / duplicate elements
    scripts/bootstrap_dirs.py     creates storage, logs, uploads
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipClean,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch5"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch5 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

Write-Step "1/6  Bootstrap operational folders"
if ($DryRun) { Write-Dry "would create storage, logs, uploads, _eval" }
else {
    $bs = Join-Path $PatchDir "scripts\bootstrap_dirs.py"
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($bs),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path "scripts\bootstrap_dirs.py" -Content $c
    & $py.Source "scripts/bootstrap_dirs.py"
}

Write-Step "2/6  Install files"
$files = @(
  @{ p = "packages\search\reranker.py";        n = "scale-aware, no noise boost" },
  @{ p = "packages\search\filters.py";         n = "relative thresholds" },
  @{ p = "packages\schemas\contracts.py";      n = "21 contracts" },
  @{ p = "packages\schemas\__init__.py";       n = "single import surface" },
  @{ p = "scripts\clean_index_quality.py";     n = "exclude blank / noise / duplicates" },
  @{ p = "tests\unit\test_contracts.py";       n = "10 contract tests" }
)
$bkDir = Join-Path "_backup" ("batch3-" + (Get-Stamp))
foreach ($f in $files) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Err2 ("missing: " + $f.p); continue }
    if ($DryRun) { Write-Dry ($f.p + "  - " + $f.n); continue }
    if (Test-Path -LiteralPath $f.p) {
        $bk = Join-Path $bkDir $f.p
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $f.p -Destination $bk -Force
    }
    $d = Split-Path -Parent $f.p
    if ($d -and -not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $f.p -Content $c
    Write-Ok ($f.p + "  - " + $f.n)
}
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "3/6  Syntax and contract tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in $files) {
        if ($f.p -like "*.py") {
            & $py.Source -m py_compile $f.p 2>&1 | Out-Null
            if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f.p); exit 1 }
        }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/6  Index quality report"
if ($DryRun) { Write-Dry "would run clean_index_quality.py --report" }
else {
    & $py.Source "scripts/clean_index_quality.py" --report
}

Write-Step "5/6  Apply index cleanup"
if ($DryRun) { Write-Dry "would run clean_index_quality.py --apply" }
elseif ($SkipClean) { Write-Warn2 "skipped (-SkipClean)" }
else {
    Write-Info "no rows are deleted; text_raw is never touched"
    & $py.Source "scripts/clean_index_quality.py" --apply --drop-duplicates
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "cleanup reported an error" }
}

Write-Step "6/6  Measure against baseline"
if ($DryRun) { Write-Dry "would compare against $Baseline"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline - skipping comparison"; exit 0 }

& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression."
    Write-Host "  git add -A ; git commit -m 'fix: batch 3 - score coherence, contracts, index quality'" -ForegroundColor Gray
} else {
    Write-Warn2 "Mixed or regressed. Send me the full comparison table before committing."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
