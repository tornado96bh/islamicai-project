<#
.SYNOPSIS
  Batch 12: real semantic embeddings, and stop the entity pollution at its source.
.DESCRIPTION
  Your judging session produced garbage questions:

    "................ ....... ibn Babawayh al-Qummi"
    "al-Shaykh al-mas'ala al-akhira bi-isnadihi 'an"
    "al-bayt 'alayhim al-salam li-ihya al-turath"

  Root cause: entity_filter was applied when DISPLAYING suggestions but not
  when STORING them. entities.json is full of unfiltered fragments, and the
  golden-set builder read from it.

  Two fixes plus the thing you actually asked for:

  1. entities.py now filters at LEARN time. Index dots, digit-heavy strings
     and non-entities never enter storage.

  2. build_golden.py builds questions from the DATABASE - clean matn passages
     and real headings, classified by the layout engine - and picks the most
     INFORMATIVE window rather than the middle one, so a question is not half
     a formulaic salutation.

  3. embeddings_v2.py - a real multilingual model replacing the 256-dim hashing
     whose similarity between "the Prophet Muhammad" and "the noble Messenger"
     is exactly ZERO. Same interface, so it drops in. Falls back with a logged
     warning if the model cannot load - never a silent failure.

     setup_embeddings.py downloads it and TESTS it on Arabic pairs with known
     meaning, so you judge the model on your own material, not its reputation.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$InstallModel,
    [string]$Model = "",
    [string]$PatchDir = "$PSScriptRoot\..\patch14"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch14 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch12-" + (Get-Stamp))
$snip = Join-Path $PatchDir "snippets"

function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    return (([System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))) -replace "`r`n", "`n")
}

function Invoke-SafePatch {
    param([string]$File, [string]$A, [string]$R, [string]$Label)
    if (-not (Test-Path -LiteralPath $File)) { Write-Warn2 "$Label - file missing"; return }
    $anchor = Get-Snippet $A
    $repl = Get-Snippet $R
    $text = (Read-Utf8 $File) -replace "`r`n", "`n"
    if ($repl.Length -gt 40 -and $text.Contains($repl.TrimEnd())) {
        Write-Info "$Label - already applied"; return
    }
    $i = $text.IndexOf($anchor)
    if ($i -lt 0) { Write-Err2 "$Label - anchor NOT found. Nothing changed."; return }
    if ($text.IndexOf($anchor, $i + 1) -ge 0) { Write-Err2 "$Label - anchor not unique"; return }
    if ($DryRun) { Write-Dry "$Label - would apply"; return }
    $bk = Join-Path $bkDir $File
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
    Copy-Item -LiteralPath $File -Destination $bk -Force
    Write-Utf8NoBom -Path $File -Content ($text.Replace($anchor, $repl))
    Write-Ok "$Label - applied"
}

Write-Step "1/6  Install files"
$files = @(
  @{ p = "packages\learning\embeddings_v2.py"; n = "real multilingual embeddings, safe fallback" },
  @{ p = "scripts\setup_embeddings.py";        n = "download and TEST the model on Arabic pairs" },
  @{ p = "scripts\build_golden.py";            n = "questions from the DB, not the polluted file" },
  @{ p = "tests\unit\test_batch12.py";         n = "23 tests" }
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

Write-Step "2/6  Stop entity pollution at the source"
Invoke-SafePatch -File "packages\learning\entities.py" `
    -A "entities_learn_anchor.txt" -R "entities_learn_repl.txt" `
    -Label "entities.py: storable-entity helper"
Invoke-SafePatch -File "packages\learning\entities.py" `
    -A "learn_label_anchor.txt" -R "learn_label_repl.txt" `
    -Label "entities.py: filter at learn time"

Write-Step "3/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\learning\embeddings_v2.py","packages\learning\entities.py",
                     "scripts\build_golden.py","scripts\setup_embeddings.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/6  Embedding model status"
if ($DryRun) { Write-Dry "would check the model" }
else { & $py.Source "scripts/setup_embeddings.py" --check }

Write-Step "5/6  Install and test the model"
if ($DryRun) { Write-Dry "would install and test"; exit 0 }
if ($InstallModel) {
    Write-Info "installing sentence-transformers - several minutes and about 500MB"
    & $py.Source "scripts/setup_embeddings.py" --install
    Write-Host ""
    Write-Info "testing the model on Arabic pairs with known meaning"
    if ($Model) { & $py.Source "scripts/setup_embeddings.py" --test --model $Model }
    else { & $py.Source "scripts/setup_embeddings.py" --test }
    Write-Host ""
    Write-Warn2 "READ the pair scores above. If it scores below 3 of 6, the model"
    Write-Warn2 "does not understand your corpus - try a bigger one before adopting it."
} else {
    Write-Host ""
    Write-Host "  To install and test the real model:" -ForegroundColor Cyan
    Write-Host "    .\tools\C0-batch12.ps1 -InstallModel" -ForegroundColor Gray
    Write-Host "    .\tools\C0-batch12.ps1 -InstallModel -Model intfloat/multilingual-e5-base" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Nothing changes in search until you adopt it and retrain." -ForegroundColor Yellow
    Write-Host ""
}

Write-Step "6/6  Rebuild entities, then judge again"
if (-not $DryRun) {
    Write-Host ""
    Write-Host "  The polluted entities are still stored. To rebuild them clean:" -ForegroundColor Cyan
    Write-Host "    python scripts/train_learning.py" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Then try the judging session again - the questions will be real:" -ForegroundColor Cyan
    Write-Host "    python scripts/build_golden.py --suggest 25" -ForegroundColor Gray
    Write-Host ""
}
exit 0
