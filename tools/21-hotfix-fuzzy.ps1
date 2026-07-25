<#
.SYNOPSIS
  Hotfix for the aborted-transaction error in fuzzy.py (v2.0.0 -> v2.0.1).
.DESCRIPTION
  Root cause: "SET LOCAL pg_trgm.similarity_threshold = :t" used a bind
  parameter. PostgreSQL SET does not accept bind parameters. The command
  failed, the transaction entered an aborted state, and a bare
  "except: pass" swallowed the Python error without clearing it - so every
  later query failed with InFailedSqlTransaction.

  Fix: use set_limit() (which does take a parameter), run it inside a
  SAVEPOINT so failure cannot poison the outer transaction, verify with
  show_limit(), and fall back to similarity() filtering if the threshold
  cannot be lowered.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipEval,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch4"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

Write-Step "1/4  Replace fuzzy.py"
$target = "packages\search\fuzzy.py"
$src = Join-Path $PatchDir $target
if (-not (Test-Path -LiteralPath $src)) { throw "patch file missing: $src" }

if ($DryRun) { Write-Dry "$target  - fixes aborted-transaction bug" }
else {
    $bkDir = Join-Path "_backup" ("hotfix-" + (Get-Stamp))
    New-Item -ItemType Directory -Force -Path (Join-Path $bkDir "packages\search") | Out-Null
    if (Test-Path -LiteralPath $target) {
        Copy-Item -LiteralPath $target -Destination (Join-Path $bkDir $target) -Force
    }
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $target -Content $c
    Write-Ok "$target  - v2.0.1"
    Write-Info "original saved in $bkDir"
}

Write-Step "2/4  Syntax check"
if ($DryRun) { Write-Dry "would run py_compile" }
else {
    & $py.Source -m py_compile $target 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { Write-Ok "syntax ok" } else { Write-Err2 "SYNTAX ERROR"; exit 1 }
}

Write-Step "3/4  Smoke test - one real query against the database"
if ($DryRun) { Write-Dry "would run a single fuzzy query" }
else {
    $probe = @'
import sys
from packages.database.session import SessionLocal
from packages.search.fuzzy import FuzzySearcher

db = SessionLocal()
try:
    s = FuzzySearcher(db)
    hits = s.search("alsalat", limit=5)
    print("  index operator active :", s.use_index_operator)
    hits = s.search(chr(1575)+chr(1604)+chr(1604)+chr(1607), limit=5)
    print("  hits returned         :", len(hits))
    if hits:
        print("  top result            :", (hits[0].get("text") or "")[:60])
    db.rollback()
    sys.exit(0)
except Exception as exc:
    print("  FAILED:", exc)
    sys.exit(1)
finally:
    db.close()
'@
    $probePath = Join-Path $env:TEMP "islamicai_probe.py"
    Write-Utf8NoBom -Path $probePath -Content $probe
    & $py.Source $probePath
    if ($LASTEXITCODE -eq 0) { Write-Ok "fuzzy searcher works against the live database" }
    else {
        Write-Err2 "smoke test failed - do not run the eval yet"
        Write-Warn2 "send me the error above"
        exit 1
    }
}

Write-Step "4/4  Measure against baseline"
if ($DryRun -or $SkipEval) { Write-Dry "skipping evaluation"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Err2 "no baseline at $Baseline"; exit 1 }

& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE

Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression."
    Write-Host "  git add -A ; git commit -m 'fix: batch 2b - RRF, indexed search, OCR correction'" -ForegroundColor Gray
} else {
    Write-Warn2 "Regression or mixed result. Send me the full comparison table."
}
Write-Host ""
exit $code
