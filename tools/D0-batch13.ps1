<#
.SYNOPSIS
  Batch 13: the readable text form, and hadith splitting into number / isnad / matn.
.DESCRIPTION
  Your complaint: diacritics, hamzas and dots keep getting lost. The cause is
  that only TWO forms existed:

    text_raw         original, with all marks - but stretched and fragmented
                     "qaaaal rasuuul Allah ) salaaa Allah alayhiii wa aalihii ("
    text_normalized  clean for search - but STRIPPED of every diacritic

  The third form was computed inside the pipeline and thrown away: the output
  of OCR correction BEFORE canonicalisation.

    text_display     no stretching, no fragmentation, EVERY diacritic, hamza
                     and dot preserved. This is what a reader should see.

  Plus the hadith splitter, built to the template you gave:

    [ 29214 ] 1 - Muhammad b. Ya'qub ... qala : sa'altu Aba Ja'far ( a.s. )
              ^number   ^--------------- isnad ----------------------^
    'an rajulin dabbara mamlukan lahu ...
    ^--------------------- matn -------

  The isnad ends AFTER the Imam's honorific, not at the first "qala" - because
  "qala : sa'altu Aba Ja'far" is the narrator speaking, not the matn.

  Strict rule enforced by a test: reassembling the parts must reproduce the
  original BYTE FOR BYTE. Nothing is ever dropped.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Apply,
    [double]$MinConfidence = 0.5,
    [string]$PatchDir = "$PSScriptRoot\..\patch15"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch15 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch13-" + (Get-Stamp))
$snip = Join-Path $PatchDir "snippets"

function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    return (([System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))) -replace "`r`n", "`n")
}

Write-Step "1/6  Install files"
$files = @(
  @{ p = "packages\layout\hadith_splitter.py";  n = "number / isnad / matn, byte-exact" },
  @{ p = "packages\database\models\page_element.py"; n = "text_display + hadith columns" },
  @{ p = "alembic\versions\b2c3d4e5f6a7_add_text_display.py"; n = "migration" },
  @{ p = "scripts\backfill_display_and_split.py"; n = "fills the readable form and the split" },
  @{ p = "tests\unit\test_hadith_splitter.py";    n = "21 tests on YOUR example" }
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

Write-Step "2/6  Expose the readable form in results"
$target = "packages\search\models.py"
if (Test-Path -LiteralPath $target) {
    $anchor = Get-Snippet "models_display_anchor.txt"
    $repl = Get-Snippet "models_display_repl.txt"
    $text = (Read-Utf8 $target) -replace "`r`n", "`n"
    if ($text.Contains("text_display")) { Write-Info "models.py - already applied" }
    elseif ($text.IndexOf($anchor) -lt 0) {
        Write-Err2 "models.py - anchor NOT found (batch 7 required). Nothing changed."
    }
    elseif ($DryRun) { Write-Dry "models.py - would add text_display and hadith fields" }
    else {
        $bk = Join-Path $bkDir $target
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $target -Destination $bk -Force
        Write-Utf8NoBom -Path $target -Content ($text.Replace($anchor, $repl))
        Write-Ok "models.py - results now carry text_display, isnad_text, matn_text"
    }
}

Write-Step "3/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\layout\hadith_splitter.py","packages\search\models.py",
                     "packages\database\models\page_element.py",
                     "scripts\backfill_display_and_split.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/6  Migration"
if ($DryRun) { Write-Dry "would run alembic upgrade head" }
elseif (-not $Apply) { Write-Warn2 "NOT applied (no -Apply). Adds 5 columns, drops nothing." }
else {
    & $py.Source -m alembic upgrade head
    if ($LASTEXITCODE -ne 0) { Write-Err2 "migration failed. Revert: alembic downgrade -1"; exit 1 }
    Write-Ok "columns added: text_display, hadith_number, isnad_text, matn_text, split_confidence"
}

Write-Step "5/6  Preview the result on your own data"
if ($DryRun) { Write-Dry "would show a sample"; exit 0 }
if (-not $Apply) {
    & $py.Source "scripts/backfill_display_and_split.py" --dry-run
    Write-Host ""
    Write-Host "  To apply:  .\tools\D0-batch13.ps1 -Apply" -ForegroundColor Cyan
    Write-Host ""
    exit 0
}

Write-Step "6/6  Fill the readable form and the split"
Write-Info "text_raw is never touched; every part is a literal slice of it"
& $py.Source "scripts/backfill_display_and_split.py" --apply --min-confidence $MinConfidence
if ($LASTEXITCODE -ne 0) { Write-Err2 "backfill failed"; exit 1 }

Write-Host ""
Write-Ok "Done. Search results now carry:"
Write-Host "    text           the original, for citation - untouched" -ForegroundColor Gray
Write-Host "    text_display   readable, WITH all diacritics and hamzas" -ForegroundColor Gray
Write-Host "    isnad_text     the chain" -ForegroundColor Gray
Write-Host "    matn_text      the text of the report" -ForegroundColor Gray
Write-Host ""
Write-Host "  git add -A ; git commit -m 'feat: batch 13 - readable text form and hadith splitting'" -ForegroundColor Gray
Write-Host ""
exit 0
