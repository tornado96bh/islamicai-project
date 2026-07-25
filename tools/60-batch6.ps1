<#
.SYNOPSIS
  Batch 6: rebuild the learning layer from corrected text; clean entity names; OR fallback for FTS.
.DESCRIPTION
  Root cause your last run exposed: entity labels like "Muhammad b. Ya'qub 'an"
  are polluted because trainer.py learns from element.text - the ORIGINAL
  uncorrected column - not from text_normalized. That is why the letter "d"
  alone has frequency 16,359 while the correct "Muhammad" has 2,651.

  Changes:
    trainer.py        learn from text_normalized; skip footnotes for entities
    entity_filter.py  strip trailing transmission particles; never strip "Ali"
    fts.py            OR fallback when an AND query returns nothing
    then a full retrain from the cleaned text
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipRetrain,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch8"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch8 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$snip = Join-Path $PatchDir "snippets"
function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    return (([System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))) -replace "`r`n", "`n")
}

Write-Step "1/6  Install files"
$files = @(
  @{ p = "packages\learning\entity_filter.py"; n = "v1.1.0 - trailing particles, Ali guard" },
  @{ p = "packages\search\fts.py";             n = "OR fallback for multi-word queries" },
  @{ p = "tests\unit\test_batch6.py";          n = "19 tests" }
)
$bkDir = Join-Path "_backup" ("batch6-" + (Get-Stamp))
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

Write-Step "2/6  Patch trainer.py to learn from corrected text"
if (-not $DryRun -and (Test-Path "packages\learning\trainer.py")) {
    $bk = Join-Path $bkDir "packages\learning\trainer.py"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
    Copy-Item -LiteralPath "packages\learning\trainer.py" -Destination $bk -Force
}
$anchor = Get-Snippet "trainer_anchor.txt"
$repl   = Get-Snippet "trainer_repl.txt"
$file   = "packages\learning\trainer.py"
if (-not (Test-Path -LiteralPath $file)) { Write-Err2 "trainer.py missing"; exit 1 }
$text = (Read-Utf8 $file) -replace "`r`n", "`n"
if ($text.Contains("text_normalized") -and $text.Contains("_REFERENCE_LAYOUTS")) {
    Write-Info "trainer.py - already patched"
} else {
    $i = $text.IndexOf($anchor)
    if ($i -lt 0) { Write-Err2 "trainer.py - anchor NOT found. Nothing changed."; exit 1 }
    if ($text.IndexOf($anchor, $i + 1) -ge 0) { Write-Err2 "trainer.py - anchor not unique"; exit 1 }
    if ($DryRun) { Write-Dry "trainer.py - would apply" }
    else {
        Write-Utf8NoBom -Path $file -Content ($text.Replace($anchor, $repl))
        Write-Ok "trainer.py - now learns from text_normalized, skips footnotes for entities"
    }
}
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "3/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\learning\trainer.py","packages\learning\entity_filter.py","packages\search\fts.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/6  Archive the polluted learning files"
if ($DryRun) { Write-Dry "would move storage/learning/*.json aside" }
else {
    $old = Join-Path $bkDir "storage-learning"
    New-Item -ItemType Directory -Force -Path $old | Out-Null
    $moved = 0
    Get-ChildItem "storage\learning\*.json" -ErrorAction SilentlyContinue | ForEach-Object {
        Move-Item $_.FullName -Destination $old -Force
        $moved++
    }
    Write-Ok "archived $moved learning file(s) - they were built from uncorrected text"
}

Write-Step "5/6  Full retrain from corrected text"
if ($DryRun) { Write-Dry "would run scripts/train_learning.py" }
elseif ($SkipRetrain) { Write-Warn2 "skipped (-SkipRetrain). Entity names stay polluted." }
elseif (-not (Test-Path "scripts\train_learning.py")) {
    Write-Warn2 "scripts/train_learning.py not found - retrain manually"
} else {
    Write-Info "this rebuilds dictionary, phrases, entities and embeddings"
    & $py.Source "scripts/train_learning.py"
    if ($LASTEXITCODE -eq 0) { Write-Ok "retrain complete" }
    else { Write-Warn2 "retrain reported an error - old files are in $bkDir" }
}

Write-Step "6/6  Measure against baseline"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression."
    Write-Host "  git add -A ; git commit -m 'fix: batch 6 - retrain from corrected text, entity name cleanup'" -ForegroundColor Gray
} else {
    Write-Warn2 "Mixed or regressed. Send me the comparison."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
