<#
.SYNOPSIS
  Batch 8: iterative split-word repair, and fix the latency regression.
.DESCRIPTION
  Two problems your last run exposed.

  1. LATENCY REGRESSION: 992ms -> 2506ms. The eval reported "no regression"
     only because it compares against the ORIGINAL baseline of 6099ms.
     Cause: the OR fallback fired for EVERY candidate query, doubling the
     database round trips from 16 to 32. It now runs for the primary query
     only, which is all it was ever meant to rescue.

  2. "ham , ad" and "muham d" survived in search_text. Root cause is a closed
     loop: the corrector needs the correct word present in the lexicon before
     it dares to join two fragments, but the lexicon is built from the very
     text where that word is split.

     Fix: iterate. Each pass joins what it can, which raises the frequency of
     correct forms, which lets the next pass be bolder. Stops on convergence.
     The new script derives its vocabulary directly from text_normalized, so
     it does not inherit any pollution from the learning files.

  text_raw is never touched.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipRepair,
    [int]$Iterations = 3,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch10"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch10 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch8-" + (Get-Stamp))

Write-Step "1/6  Install files"
$files = @(
  @{ p = "packages\search\fts.py";            n = "OR fallback for the primary query only" },
  @{ p = "scripts\repair_split_words.py";     n = "iterative self-feeding split repair" },
  @{ p = "tests\unit\test_batch8.py";         n = "19 tests" }
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

Write-Step "2/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\search\fts.py","scripts\repair_split_words.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "3/6  Split-repair report (no writes)"
if ($DryRun) { Write-Dry "would run repair_split_words.py --report" }
else { & $py.Source "scripts/repair_split_words.py" --report }

Write-Step "4/6  Apply iterative repair"
if ($DryRun) { Write-Dry "would run repair_split_words.py --apply" }
elseif ($SkipRepair) { Write-Warn2 "skipped (-SkipRepair)" }
else {
    Write-Info "text_raw stays untouched; only text_normalized is repaired"
    & $py.Source "scripts/repair_split_words.py" --apply --iterations $Iterations
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "repair reported an error" }
}

Write-Step "5/6  Retrain on the repaired text"
if ($DryRun) { Write-Dry "would archive learning files and retrain" }
elseif ($SkipRepair) { Write-Warn2 "skipped" }
else {
    $old = Join-Path $bkDir "storage-learning"
    New-Item -ItemType Directory -Force -Path $old | Out-Null
    Get-ChildItem "storage\learning\*.json" -ErrorAction SilentlyContinue |
        ForEach-Object { Move-Item $_.FullName -Destination $old -Force }
    & $py.Source "scripts/train_learning.py"
    if ($LASTEXITCODE -eq 0) { Write-Ok "retrain complete" }
    else { Write-Warn2 "retrain error - old files are in $bkDir" }
}

Write-Step "6/6  Measure"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
Write-Warn2 "WATCH latency_ms_p50. The previous run was 2506ms after a 992ms run."
Write-Warn2 "The comparison below is against the ORIGINAL 6099ms baseline, so it"
Write-Warn2 "can say 'no regression' while still being slower than two runs ago."
& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression against the original baseline."
    Write-Host "  git add -A ; git commit -m 'fix: batch 8 - iterative split repair, latency fix'" -ForegroundColor Gray
} else {
    Write-Warn2 "Send me the comparison."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
