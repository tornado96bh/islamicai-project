<#
.SYNOPSIS
  Batch 5: fix the slow fuzzy path, correct layout misclassifications, wire the entity filter.
.DESCRIPTION
  Driven entirely by what your own measurement exposed:

  1. set_limit(double precision) does not exist -> fuzzy silently fell back to
     the slow non-indexed path. The fix casts the threshold to REAL, which is
     the only type set_limit accepts. Expect a further latency drop.

  2. Layout misclassifications seen in your review sample:
       "10 - al-Zuhd / 27 : 291 ."   was matn      -> now footnote
       "kitab al-mudaraba ."         was matn      -> now heading
       "al-Sa'dabadi , 'an Ahmad..."  was unknown   -> now sanad

  3. entity_filter was written in batch 3 but never wired, so "min al-bab"
     and "fi al-hadith" were still surfacing as entities. Now connected.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipReclassify,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch7"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch7 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$snip = Join-Path $PatchDir "snippets"
function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    $t = [System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))
    return ($t -replace "`r`n", "`n")
}

function Invoke-SafePatch {
    param([string]$File, [string]$Anchor, [string]$Replacement, [string]$Label, [switch]$DryRun)
    if (-not (Test-Path -LiteralPath $File)) { Write-Warn2 "$Label - file missing"; return $false }
    $orig = Read-Utf8 $File
    $text = $orig -replace "`r`n", "`n"
    if ($Replacement.Length -gt 40 -and $text.Contains($Replacement.TrimEnd())) {
        Write-Info "$Label - already applied"; return $true
    }
    $i = $text.IndexOf($Anchor)
    if ($i -lt 0) { Write-Err2 "$Label - anchor NOT found. Nothing changed."; return $false }
    if ($text.IndexOf($Anchor, $i + 1) -ge 0) { Write-Err2 "$Label - anchor not unique. Aborted."; return $false }
    if ($DryRun) { Write-Dry "$Label - would apply"; return $true }
    Write-Utf8NoBom -Path $File -Content ($text.Replace($Anchor, $Replacement))
    Write-Ok "$Label - applied"
    return $true
}

Write-Step "1/6  Install updated files"
$files = @(
  @{ p = "packages\search\fuzzy.py";           n = "v2.0.2 - REAL cast so the trigram index is used" },
  @{ p = "packages\layout\classifier.py";      n = "v1.1.0 - fixes from your review sample" },
  @{ p = "packages\learning\entity_filter.py"; n = "entity filter" },
  @{ p = "tests\unit\test_layout_v11.py";      n = "layout regression tests" },
  @{ p = "tests\unit\test_entity_wiring.py";   n = "entity filter tests" }
)
$bkDir = Join-Path "_backup" ("batch5-" + (Get-Stamp))
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

Write-Step "2/6  Wire entity filter into entities.py"
if (-not $DryRun -and (Test-Path "packages\learning\entities.py")) {
    $bk = Join-Path $bkDir "packages\learning\entities.py"
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
    Copy-Item -LiteralPath "packages\learning\entities.py" -Destination $bk -Force
}
Invoke-SafePatch -File "packages\learning\entities.py" `
    -Anchor (Get-Snippet "entities_import_anchor.txt") `
    -Replacement (Get-Snippet "entities_import_repl.txt") `
    -Label "entities.py: import filter" -DryRun:$DryRun | Out-Null
Invoke-SafePatch -File "packages\learning\entities.py" `
    -Anchor (Get-Snippet "entities_anchor.txt") `
    -Replacement (Get-Snippet "entities_repl.txt") `
    -Label "entities.py: filter suggestions" -DryRun:$DryRun | Out-Null

Write-Step "3/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\search\fuzzy.py","packages\layout\classifier.py",
                     "packages\learning\entity_filter.py","packages\learning\entities.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/6  Smoke test - is the trigram index active now?"
if ($DryRun) { Write-Dry "would probe the database" }
else {
    $probe = @'
import sys
from packages.database.session import SessionLocal
from packages.search.fuzzy import FuzzySearcher
db = SessionLocal()
try:
    s = FuzzySearcher(db)
    hits = s.search(chr(1575)+chr(1604)+chr(1604)+chr(1607), limit=5)
    print("  index operator active :", s.use_index_operator)
    print("  hits returned         :", len(hits))
    db.rollback()
    sys.exit(0 if s.use_index_operator and hits else 1)
except Exception as exc:
    print("  FAILED:", exc); sys.exit(2)
finally:
    db.close()
'@
    $pp = Join-Path $env:TEMP "islamicai_probe5.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
    if ($LASTEXITCODE -eq 0) { Write-Ok "trigram index is now used - expect faster search" }
    elseif ($LASTEXITCODE -eq 1) { Write-Warn2 "still on the fallback path - send me the output" }
    else { Write-Err2 "probe failed"; exit 1 }
}

Write-Step "5/6  Re-classify layout with v1.1.0"
if ($DryRun) { Write-Dry "would re-run classify_layout.py --apply" }
elseif ($SkipReclassify) { Write-Warn2 "skipped (-SkipReclassify)" }
else {
    & $py.Source "scripts/classify_layout.py" --apply
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "re-classification reported an error" }
}

Write-Step "6/6  Measure against baseline"
if ($DryRun) { Write-Dry "would compare"; exit 0 }
if (-not (Test-Path $Baseline)) { Write-Warn2 "no baseline"; exit 0 }
& $py.Source "scripts/eval_search.py" --compare $Baseline
$code = $LASTEXITCODE
Write-Host ""
if ($code -eq 0) {
    Write-Ok "No regression."
    Write-Host "  git add -A ; git commit -m 'fix: batch 5 - trgm index, layout v1.1, entity filter wiring'" -ForegroundColor Gray
} else {
    Write-Warn2 "Mixed or regressed. Send me the comparison."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
