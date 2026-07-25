<#
.SYNOPSIS
  Batch 4: Layout Engine - the keystone that unblocks Isnad, Hadith and Narrator.
.DESCRIPTION
  Every element in the database is currently element_type="text". Consequences:
    - the noisy entities ("min al-bab", "fi al-hadith") all come from FOOTNOTES,
      but nothing distinguishes a footnote from matn
    - no isnad can be extracted without knowing where sanad ends and matn begins
    - the Hadith and Isnad contracts cannot be filled
    - ranking cannot prefer matn over a running head

  This batch classifies elements into matn / sanad / footnote / takhrij /
  heading / running_head / page_number, writes the result into element_type
  and layout_confidence, and wires a small layout bonus into ranking.

  IMPORTANT: run -Review FIRST and judge a random sample yourself. This is a
  rule-based classifier, not a trained model. 30/30 on hand-picked samples is
  NOT the same as accuracy over 13,916 elements.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply,
    [int]$Review = 30,
    [double]$MinConfidence = 0.55,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch6"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch6 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

Write-Step "1/5  Install layout engine"
$files = @(
  @{ p = "packages\layout\classifier.py";  n = "rule-based Arabic layout classifier" },
  @{ p = "packages\layout\__init__.py";    n = "package marker" },
  @{ p = "packages\search\ranking.py";     n = "v2.1.0 - layout-aware ranking" },
  @{ p = "scripts\classify_layout.py";     n = "classify + review sampler" },
  @{ p = "tests\unit\test_layout.py";      n = "30 tests" }
)
$bkDir = Join-Path "_backup" ("batch4-" + (Get-Stamp))
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

Write-Step "2/5  Syntax and tests"
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

Write-Step "3/5  Distribution report"
if ($DryRun) { Write-Dry "would run classify_layout.py --report" }
else { & $py.Source "scripts/classify_layout.py" --report --min-confidence $MinConfidence }

Write-Step "4/5  Human review sample"
if ($DryRun) { Write-Dry "would show $Review random samples" }
elseif ($Review -gt 0) {
    & $py.Source "scripts/classify_layout.py" --review $Review --min-confidence $MinConfidence
    Write-Host ""
    Write-Warn2 "READ THE SAMPLE ABOVE. You are the domain expert, not the classifier."
    Write-Warn2 "If the labels look wrong, stop here and send them to me."
    Write-Host ""
}

Write-Step "5/5  Apply classification"
if ($DryRun) { Write-Dry "would run classify_layout.py --apply"; exit 0 }
if (-not $Apply) {
    Write-Warn2 "NOT applied (no -Apply flag). Review the sample first, then run:"
    Write-Host "    .\tools\40-layout-engine.ps1 -Apply" -ForegroundColor Cyan
    exit 0
}

& $py.Source "scripts/classify_layout.py" --apply --min-confidence $MinConfidence
if ($LASTEXITCODE -ne 0) { Write-Err2 "classification failed"; exit 1 }
Write-Ok "element_type and layout_confidence updated"

if (Test-Path $Baseline) {
    Write-Step "Measure against baseline"
    & $py.Source "scripts/eval_search.py" --compare $Baseline
    $code = $LASTEXITCODE
    Write-Host ""
    if ($code -eq 0) {
        Write-Ok "No regression."
        Write-Host "  git add -A ; git commit -m 'feat: batch 4 - layout engine'" -ForegroundColor Gray
    } else {
        Write-Warn2 "Mixed or regressed. Send me the comparison before committing."
        Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
    }
    exit $code
}
exit 0
