<#
.SYNOPSIS
  Install batch 2 modules. ADDITIVE ONLY - does not change search behaviour yet.
.DESCRIPTION
  Installs four tested modules plus the eval harness:
    packages/ingestion/ocr_corrector.py   stretch, ligatures, intra-word splits
    packages/search/fusion.py             RRF - fixes the ranking regression
    packages/learning/entity_filter.py    rejects "min al-bab" style non-entities
    scripts/eval_search.py                measurement gate
    datasets/golden/queries.jsonl         seed golden set

  Nothing is wired into the engine by this script. That is deliberate:
  a baseline measurement must exist BEFORE behaviour changes, otherwise
  we repeat the mistake that caused the ranking regression.
#>
[CmdletBinding()]
param([switch]$DryRun, [string]$PatchDir = "$PSScriptRoot\..\patch2")
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch2 folder not found: $PatchDir" }

Write-Step "1/4  Copy batch 2 files"
$files = @(
  @{ p = "packages\ingestion\ocr_corrector.py";  n = "OCR corrector (stretch / ligature / split repair)" },
  @{ p = "packages\search\fusion.py";            n = "RRF fusion - fixes ranking regression" },
  @{ p = "packages\learning\entity_filter.py";   n = "entity filter" },
  @{ p = "scripts\eval_search.py";               n = "eval harness" },
  @{ p = "datasets\golden\queries.jsonl";        n = "seed golden queries" },
  @{ p = "datasets\golden\README.md";            n = "how to build the golden set" },
  @{ p = "tests\unit\test_batch2.py";            n = "40 tests" }
)
$bkDir = Join-Path "_backup" ("batch2-" + (Get-Stamp))
foreach ($f in $files) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Err2 ("missing patch file: " + $f.p); continue }
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

Write-Step "2/4  Ensure package markers"
foreach ($d in @("packages\ingestion", "packages\search", "packages\learning", "tests\unit")) {
    $init = Join-Path $d "__init__.py"
    if ((Test-Path -LiteralPath $d) -and -not (Test-Path -LiteralPath $init)) {
        if ($DryRun) { Write-Dry "would create $init" }
        else { Write-Utf8NoBom -Path $init -Content ""; Write-Ok "created $init" }
    }
}

Write-Step "3/4  Syntax check"
$py = Get-Python
if (-not $py) { Write-Warn2 "python not found - skipping" }
elseif ($DryRun) { Write-Dry "would run py_compile" }
else {
    foreach ($f in $files) {
        if ($f.p -like "*.py" -and (Test-Path -LiteralPath $f.p)) {
            & $py.Source -m py_compile $f.p 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok ("syntax ok: " + $f.p) }
            else { Write-Err2 ("SYNTAX ERROR: " + $f.p) }
        }
    }
}

Write-Step "4/4  Run batch 2 tests"
if ($py -and -not $DryRun) {
    & $py.Source -m pytest "tests/unit/test_batch2.py" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all 40 batch 2 tests passed" }
    else { Write-Err2 "tests failed - review output"; Write-Warn2 "revert: git checkout -- packages/ scripts/ tests/ datasets/" }
}

Write-Host ""
Write-Host "  Nothing is wired yet - search behaviour is unchanged." -ForegroundColor Yellow
Write-Host "  Next:  .\tools\11-baseline.ps1" -ForegroundColor Cyan
Write-Host ""
