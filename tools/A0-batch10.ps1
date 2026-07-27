<#
.SYNOPSIS
  Batch 10: fix a design error I introduced in batch 9 - short clean text was rewarded.
.DESCRIPTION
  Batch 9 raised must_contain_rate to 0.875, but that number HID a real
  quality regression. Two facts from your own probe:

    spread : 0.00536      <- was 0.011 BEFORE batch 9
    top 20 : dominated by "in sha Allah" boilerplate and a
             table-of-contents line "ism Allah . . . 01 768 678"

  Cause: I made ocr_quality a REWARD. A short clean line scored 1.00 while a
  long useful passage with tatweel scored 0.04. Measured correlation between
  the graded signals and rrf_base was -0.93 - they cancelled the base instead
  of complementing it.

  And must_contain_rate went UP because every one of those boilerplate lines
  contains the query word. The metric rewarded the regression.

  Fix:
    1. ocr_quality is now a PENALTY only. Clean text gets zero, not a bonus.
    2. length_prior     - a four word line is rarely the best answer.
    3. informativeness  - text made of formulaic phrases is demoted.
    4. index-line detection - dot runs and trailing page numbers.

  Measured on your own twenty results:
    correlation with rrf_base : -0.93  ->  +0.17
    total spread              : 0.00505 -> 0.01578
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch12"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch12 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch10-" + (Get-Stamp))

Write-Step "1/4  Install files"
$files = @(
  @{ p = "packages\search\signals.py";        n = "v1.1.0 - penalty not reward, length and informativeness" },
  @{ p = "packages\search\ranking.py";        n = "v2.3.0" },
  @{ p = "tests\unit\test_signals_v11.py";    n = "21 tests" }
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

Write-Step "3/4  Quality probe - THIS is the real check, not the eval"
if ($DryRun) { Write-Dry "would probe" }
else {
    $probe = @'
import sys
from packages.database.session import SessionLocal
from packages.search.engine import SearchEngine
db = SessionLocal()
BOIL = ("an sha", chr(1575)+chr(1606)+" "+chr(1588)+chr(1575),
        chr(1575)+chr(1604)+chr(1581)+chr(1605)+chr(1583))
try:
    payload = SearchEngine(db).search(chr(1575)+chr(1604)+chr(1604)+chr(1607), limit=20)
    rows = payload.get("results", [])
    if not rows:
        print("  no results"); sys.exit(1)
    scores = [r.get("score", 0.0) for r in rows]
    print("  results      :", len(rows))
    print("  spread       : %.5f   (batch 9 gave 0.00536)" % (max(scores) - min(scores)))
    lens = [len((r.get("search_text") or "").split()) for r in rows]
    print("  median words : %d   (short-text bias check)" % sorted(lens)[len(lens)//2])
    boiler = sum(1 for r in rows
                 if any(b in (r.get("search_text") or "") for b in BOIL))
    print("  boilerplate  : %d of 20   (lower is better)" % boiler)
    print("")
    print("  TOP 5:")
    for r in rows[:5]:
        print("   ", (r.get("search_text") or "")[:70])
    db.rollback(); sys.exit(0)
except Exception as exc:
    print("  FAILED:", exc); sys.exit(2)
finally:
    db.close()
'@
    $pp = Join-Path $env:TEMP "islamicai_probe10.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
}

Write-Step "4/4  Measure"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
Write-Warn2 "must_contain_rate may DROP, and that can be correct."
Write-Warn2 "For the query 'Allah' every boilerplate line contains the word, so"
Write-Warn2 "the metric rewarded them. Judge by the TOP 5 above, not the number."
& $py.Source "scripts/eval_search.py" --compare $Baseline
Write-Host ""
Write-Host "  git add -A ; git commit -m 'fix: batch 10 - ocr as penalty, length and informativeness signals'" -ForegroundColor Gray
Write-Host ""
exit 0
