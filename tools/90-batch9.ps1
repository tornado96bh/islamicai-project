<#
.SYNOPSIS
  Batch 9: make ranking actually discriminate, and stop one page dominating.
.DESCRIPTION
  Your standing complaint: score_final sits between 0.078 and 0.089 for every
  result, so the reader cannot tell an excellent hit from a mediocre one.

  Cause: every signal was binary. For a common query like "Allah" all of them
  fire on every result, so they became a CONSTANT OFFSET, not a signal:

      signals 0.022   exact_raw 0.020   layout 0.012   rerank 0.014

  Only rrf_base varied, and its range was just 0.0099.

  Fix: graded signals computed from the result itself
      ocr_quality     tatweel density, fragments, punctuation inside words
      coverage        fraction of query words present, not just "any"
      completeness    is it a whole sentence or a cut fragment
      density         how central the query is to the passage

  Measured on your own twenty results, these span 0.016 to 0.028, which
  roughly doubles the discriminating range. Weights stay inside the RRF
  scale - the lesson from batch 3.

  Also: at most 3 results per page in the primary block, so one page cannot
  crowd out coverage of the rest of the book.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch11"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch11 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch9-" + (Get-Stamp))

Write-Step "1/4  Install files"
$files = @(
  @{ p = "packages\search\signals.py";   n = "graded ranking signals" },
  @{ p = "packages\search\ranking.py";   n = "v2.2.0 - graded signals + page diversity" },
  @{ p = "tests\unit\test_signals.py";   n = "18 tests" }
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

Write-Step "2/4  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\search\signals.py","packages\search\ranking.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "3/4  Score spread probe"
if ($DryRun) { Write-Dry "would probe score spread" }
else {
    $probe = @'
import sys
from packages.database.session import SessionLocal
from packages.search.engine import SearchEngine
db = SessionLocal()
try:
    payload = SearchEngine(db).search(chr(1575)+chr(1604)+chr(1604)+chr(1607), limit=20)
    rows = payload.get("results", [])
    if not rows:
        print("  no results"); sys.exit(1)
    scores = [r.get("score", 0.0) for r in rows]
    pages = {}
    for r in rows:
        k = str(r.get("page_id"))
        pages[k] = pages.get(k, 0) + 1
    print("  results        :", len(rows))
    print("  top score      : %.5f" % max(scores))
    print("  bottom score   : %.5f" % min(scores))
    print("  spread         : %.5f" % (max(scores) - min(scores)))
    print("  max per page   :", max(pages.values()))
    ex = rows[0].get("score_explain", {})
    graded = [r.get("score_explain", {}).get("graded_signals") for r in rows]
    graded = [g for g in graded if g is not None]
    if graded:
        print("  graded signals : %.5f to %.5f" % (min(graded), max(graded)))
    db.rollback()
    sys.exit(0)
except Exception as exc:
    print("  FAILED:", exc); sys.exit(2)
finally:
    db.close()
'@
    $pp = Join-Path $env:TEMP "islamicai_probe9.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
    if ($LASTEXITCODE -eq 0) { Write-Ok "probe ok" }
    else { Write-Warn2 "probe failed - send me the output" }
}

Write-Step "4/4  Measure"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression."
    Write-Host "  git add -A ; git commit -m 'feat: batch 9 - graded ranking signals, page diversity'" -ForegroundColor Gray
} else {
    Write-Warn2 "Send me the comparison."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
