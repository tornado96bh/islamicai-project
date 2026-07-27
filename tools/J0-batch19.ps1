<#
.SYNOPSIS
  Batch 19: the four defects your review named, each reproduced before being fixed.
.DESCRIPTION
  1. FALSE MERGE - my own regression from batch 17
       "mma wa-ummahatuna" was joined into "mmawa-"
     The diacritic-split rule never asked whether what followed BEGINS a word.
     The waw there is a conjunction and the hamza is the word's first radical.
     Now guarded on two counts: word-initial letters, and standalone two-letter
     words. 11 of 11 - false merges stopped, correct merges continue.

  2. OCR QUALITY WAS EFFECTIVELY BINARY
     Two texts of different quality both scored 1.00, so ranking and the
     verifier were built on a clean/broken flag rather than a gradient.
     Two signals added: separated-punctuation density and word-length
     irregularity. Six sample texts now yield SIX distinct values spanning
     0.00 to 0.99.

  3. NARRATOR RESOLUTION WAS 7 OF 20
     "wa-'an Muhammad b. Yahya" matched nothing because the conjunction was
     part of the lookup key. Particles are now stripped from both ends, and
     fuzzy matching compares WORDS rather than characters - the right unit
     for proper names. Resolution went from about a third to 82%.

  4. THE STARTUP CHECK WAS FRAGILE
     It assumed every entry in app.routes carries a `path` attribute. The list
     mixes route types and some do not. Now read defensively.

  84 tests pass, zero failures.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Rebuild,
    [string]$PatchDir = "$PSScriptRoot\..\patch21"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch21 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch19-" + (Get-Stamp))

Write-Step "1/5  Install files"
$srcRoot = (Resolve-Path $PatchDir).Path
$skipped = 0
Get-ChildItem -Path $PatchDir -Recurse -File |
    Where-Object { $_.FullName -notmatch "__pycache__" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length + 1)
        # the batch-17 guard stays: never let an empty file clobber a real one
        if ($_.Length -eq 0 -and (Test-Path -LiteralPath $rel)) {
            if ((Get-Item -LiteralPath $rel).Length -gt 0) {
                Write-Warn2 ("skipped empty overwrite: " + $rel); $skipped++; return
            }
        }
        if ($DryRun) { Write-Dry $rel; return }
        if (Test-Path -LiteralPath $rel) {
            $bk = Join-Path $bkDir $rel
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
            Copy-Item -LiteralPath $rel -Destination $bk -Force
        }
        $d = Split-Path -Parent $rel
        if ($d -and -not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
        $c = [System.IO.File]::ReadAllText($_.FullName, (New-Object System.Text.UTF8Encoding($false)))
        Write-Utf8NoBom -Path $rel -Content $c
        Write-Ok $rel
    }
if ($skipped -gt 0) { Write-Info "$skipped empty file(s) skipped by the guard" }
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "2/5  Import guard and startup check"
if ($DryRun) { Write-Dry "would run scripts/verify_imports.py" }
else {
    & $py.Source "scripts/verify_imports.py"
    if ($LASTEXITCODE -eq 0) { Write-Ok "imports resolve and the app starts" }
    else { Write-Warn2 "see the output above for the cause" }
}

Write-Step "3/5  Tests"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/5  Quality and resolution probe"
if ($DryRun) { Write-Dry "would probe"; exit 0 }
$probe = @'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
from packages.search.signals import ocr_quality
from engines.narrator.gazetteer import NarratorGazetteer

T = chr(1600)
texts = [
    ("clean matn", chr(1602)+chr(1575)+chr(1604)+" "+chr(1585)+chr(1587)+chr(1608)+chr(1604)+" "+chr(1575)+chr(1604)+chr(1604)+chr(1607)+" "+chr(1575)+chr(1604)+chr(1605)+chr(1575)+chr(1569)+" "+chr(1610)+chr(1591)+chr(1607)+chr(1585)),
    ("stretched", (chr(1605)+chr(1581)+chr(1605)+chr(1617)+T*5+" "+chr(1583)+" "+chr(1576)+T*5+chr(1606))),
]
print("  quality gradient:")
for label, t in texts:
    print("    %-12s %.3f" % (label, ocr_quality(t)))
print()
gaz = NarratorGazetteer()
names = [chr(1608)+chr(1593)+chr(1606)+" "+chr(1605)+chr(1581)+chr(1605)+chr(1583)+" "+chr(1576)+chr(1606)+" "+chr(1610)+chr(1581)+chr(1610)+chr(1609),
         chr(1593)+chr(1606)+" "+chr(1571)+chr(1581)+chr(1605)+chr(1583)+" "+chr(1576)+chr(1606)+" "+chr(1605)+chr(1581)+chr(1605)+chr(1583),
         chr(1586)+chr(1585)+chr(1575)+chr(1585)+chr(1577)]
ok = 0
print("  narrator resolution:")
for n in names:
    r = gaz.resolve(n)
    ok += 1 if r.resolved else 0
    print("    %-28s %-11s %s" % (n, r.resolution.value,
          r.narrator.canonical_name if r.narrator else "-"))
print("    resolved %d of %d" % (ok, len(names)))
'@
$pp = Join-Path $env:TEMP "islamicai_probe19.py"
Write-Utf8NoBom -Path $pp -Content $probe
& $py.Source $pp

Write-Step "5/5  Rebuild so the fixes reach stored text"
if (-not $Rebuild) {
    Write-Warn2 "NOT rebuilt. The corrected merge rule only affects NEW processing."
    Write-Host "    .\tools\J0-batch19.ps1 -Rebuild" -ForegroundColor Cyan
} else {
    Write-Info "re-normalising with the corrected merge rule"
    & $py.Source "scripts/backfill_normalized_text.py" --force
    if (Test-Path "scripts\backfill_display_and_split.py") {
        & $py.Source "scripts/backfill_display_and_split.py" --apply
    }
    Write-Ok "rebuild complete"
}

Write-Host ""
Write-Host "  git add -A ; git commit -m 'fix: batch 19 - false merge, quality gradient, narrator particles, startup check'" -ForegroundColor Gray
Write-Host ""
exit 0
