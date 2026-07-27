<#
.SYNOPSIS
  Batch 14: fix a bad merge I introduced, clean entity labels, stop splitting non-reports, make imports lazy.
.DESCRIPTION
  Four defects, all reproduced from YOUR latest output before being fixed.

  1. A BAD MERGE I introduced in an earlier batch:
       "naqiyyan min al-danas"  ->  "naqiyyanmin"
       "mma wa-ummahatuna"      ->  "mmawa-"
     Cause: the protected-word check ran on the SHORTER side only. The
     fragment was a single alef, so "min" - which is protected - was never
     checked at all. Now BOTH sides are checked, and letters that stand as
     words on their own are no longer treated as fragments.

  2. Entity labels contaminated with punctuation:
       "al-Nabi ) salla Allah alayhi"
     Parentheses and salutation formulas are not part of a person's name.

  3. The hadith splitter ran on every text, producing nonsense:
       matn_text = ": qala"
       matn_text = ": yu'mar bi-raj al ila al-nar"
     It now requires an actual isnad chain or a report number.

  4. IMPORT-TIME SIDE EFFECTS. session.py built a PostgreSQL engine at import,
     and packages/learning, packages/ingestion and packages/search pulled it
     in transitively. Collecting tests without a database - or without
     PyMuPDF - failed outright.
       before this batch : 0 unit tests could even be collected
       after             : 25 collected and passing
     Engines are now built on first real use. No caller changes needed.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Rebuild,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch16"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch16 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch14-" + (Get-Stamp))

Write-Step "1/5  Install files"
$files = @(
  @{ p = "packages\ingestion\ocr_corrector.py";  n = "v1.2.0 - no more false merges" },
  @{ p = "packages\learning\entity_filter.py";   n = "v1.2.0 - rejects punctuation in names" },
  @{ p = "packages\layout\hadith_splitter.py";   n = "v1.1.0 - only splits actual reports" },
  @{ p = "packages\database\session.py";         n = "lazy engine" },
  @{ p = "packages\learning\__init__.py";        n = "lazy trainer import" },
  @{ p = "packages\ingestion\__init__.py";       n = "lazy PyMuPDF import" },
  @{ p = "packages\search\__init__.py";          n = "lazy engine import" },
  @{ p = "tests\unit\test_batch14.py";           n = "25 tests" }
)
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

Write-Step "2/5  Syntax and full test suite"
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

Write-Step "3/5  Import-weight check"
if ($DryRun) { Write-Dry "would verify lazy imports" }
else {
    $probe = @'
import sys, time
t0 = time.time()
import packages.learning, packages.ingestion, packages.search
elapsed = (time.time() - t0) * 1000
from packages.database import session
built = session.get_engine.cache_info().currsize
print("  import time     : %.0f ms" % elapsed)
print("  engine built    :", "YES - still eager" if built else "no - lazy as intended")
sys.exit(0 if built == 0 else 1)
'@
    $pp = Join-Path $env:TEMP "islamicai_probe14.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
    if ($LASTEXITCODE -eq 0) { Write-Ok "imports no longer touch the database" }
    else { Write-Warn2 "an engine is still built at import - send me the output" }
}

Write-Step "4/5  Rebuild the affected data"
if ($DryRun) { Write-Dry "would re-run backfill, split and retrain" }
elseif (-not $Rebuild) {
    Write-Warn2 "NOT rebuilt. The bad merges stay in text_display until you run:"
    Write-Host "    .\tools\E0-batch14.ps1 -Rebuild" -ForegroundColor Cyan
}
else {
    Write-Info "step 1 of 3: re-normalise with the fixed corrector"
    & $py.Source "scripts/backfill_normalized_text.py" --force
    Write-Info "step 2 of 3: rebuild the readable form and the hadith split"
    if (Test-Path "scripts\backfill_display_and_split.py") {
        & $py.Source "scripts/backfill_display_and_split.py" --apply
    }
    Write-Info "step 3 of 3: retrain so entities pick up the clean text"
    $old = Join-Path $bkDir "storage-learning"
    New-Item -ItemType Directory -Force -Path $old | Out-Null
    Get-ChildItem "storage\learning\*.json" -ErrorAction SilentlyContinue |
        ForEach-Object { Move-Item $_.FullName -Destination $old -Force }
    & $py.Source "scripts/train_learning.py"
    if ($LASTEXITCODE -eq 0) { Write-Ok "rebuild complete" }
    else { Write-Warn2 "retrain error - old files are in $bkDir" }
}

Write-Step "5/5  Measure"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
& $py.Source "scripts/eval_search.py" --compare $Baseline
Write-Host ""
Write-Host "  git add -A ; git commit -m 'fix: batch 14 - merge bug, entity punctuation, split gating, lazy imports'" -ForegroundColor Gray
Write-Host ""
exit 0
