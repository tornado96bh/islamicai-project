<#
.SYNOPSIS
  Batch 7: fix narrator names split by punctuation; show corrected text; clean phrase suggestions.
.DESCRIPTION
  Your review named three defects. All three trace to one root cause and two
  display gaps:

  1. "Ahmad b. Muhamm , d" - the OCR damage inserts a COMMA INSIDE the word.
     The corrector only looked at adjacent tokens, so the comma hid the split.
     This is why narrator names stayed broken while other corrections worked.

  2. Results still showed "AllAh" in search_text because build_element_hit
     recomputed it from the raw column instead of reading text_normalized,
     which is already corrected in the index.

  3. Candidate queries like "Allah )" and "Allah ) alayhi" come from n-grams
     that learned punctuation tokens. Now filtered before learning.

  Then re-runs the backfill and a full retrain so the fixes reach the data.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipRebuild,
    [string]$Baseline = "_eval\baseline.json",
    [string]$PatchDir = "$PSScriptRoot\..\patch9"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch9 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$snip = Join-Path $PatchDir "snippets"
function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    return (([System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))) -replace "`r`n", "`n")
}

$bkDir = Join-Path "_backup" ("batch7-" + (Get-Stamp))
function Backup-File {
    param([string]$File)
    if (-not (Test-Path -LiteralPath $File)) { return }
    $bk = Join-Path $bkDir $File
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
    Copy-Item -LiteralPath $File -Destination $bk -Force
}

function Invoke-SafePatch {
    param([string]$File, [string]$AnchorName, [string]$ReplName, [string]$Label, [switch]$Optional)
    if (-not (Test-Path -LiteralPath $File)) { Write-Warn2 "$Label - file missing"; return $false }
    $anchor = Get-Snippet $AnchorName
    $repl   = Get-Snippet $ReplName
    $text   = (Read-Utf8 $File) -replace "`r`n", "`n"
    if ($repl.Length -gt 40 -and $text.Contains($repl.TrimEnd())) {
        Write-Info "$Label - already applied"; return $true
    }
    $i = $text.IndexOf($anchor)
    if ($i -lt 0) {
        if ($Optional) { Write-Warn2 "$Label - anchor not found (optional, skipped)"; return $false }
        Write-Err2 "$Label - anchor NOT found. Nothing changed."; return $false
    }
    if ($text.IndexOf($anchor, $i + 1) -ge 0) { Write-Err2 "$Label - anchor not unique. Aborted."; return $false }
    if ($DryRun) { Write-Dry "$Label - would apply"; return $true }
    Backup-File $File
    Write-Utf8NoBom -Path $File -Content ($text.Replace($anchor, $repl))
    Write-Ok "$Label - applied"
    return $true
}

Write-Step "1/6  Install OCR corrector v1.1.0"
foreach ($f in @(
    @{ p = "packages\ingestion\ocr_corrector.py"; n = "merges across an intervening comma" },
    @{ p = "tests\unit\test_batch7.py";           n = "18 tests" })) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Err2 ("missing: " + $f.p); continue }
    if ($DryRun) { Write-Dry ($f.p + "  - " + $f.n); continue }
    Backup-File $f.p
    $d = Split-Path -Parent $f.p
    if ($d -and -not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    $c = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
         (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $f.p -Content $c
    Write-Ok ($f.p + "  - " + $f.n)
}

Write-Step "2/6  Show corrected text in results"
Invoke-SafePatch -File "packages\search\models.py" `
    -AnchorName "models_anchor.txt" -ReplName "models_repl.txt" `
    -Label "models.py: prefer text_raw for display" | Out-Null
Invoke-SafePatch -File "packages\search\models.py" `
    -AnchorName "models_search_anchor.txt" -ReplName "models_search_repl.txt" `
    -Label "models.py: search_text from the index" | Out-Null

Write-Step "3/6  Stop learning punctuation into phrases"
Invoke-SafePatch -File "packages\learning\trainer.py" `
    -AnchorName "trainer_helper_anchor.txt" -ReplName "trainer_helper_repl.txt" `
    -Label "trainer.py: punctuation helper" -Optional | Out-Null
Invoke-SafePatch -File "packages\learning\trainer.py" `
    -AnchorName "trainer_tokens_anchor.txt" -ReplName "trainer_tokens_repl.txt" `
    -Label "trainer.py: filter punctuation tokens" | Out-Null

Write-Step "4/6  Syntax and tests"
if ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in @("packages\ingestion\ocr_corrector.py","packages\search\models.py","packages\learning\trainer.py")) {
        & $py.Source -m py_compile $f 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Write-Err2 ("SYNTAX ERROR: " + $f); Write-Warn2 "restore from $bkDir"; exit 1 }
    }
    Write-Ok "syntax ok"
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all unit tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "5/6  Rebuild index and learning from the fixed corrector"
if ($DryRun) { Write-Dry "would re-run backfill, layout and retrain" }
elseif ($SkipRebuild) { Write-Warn2 "skipped (-SkipRebuild). Narrator names stay broken." }
else {
    Write-Info "step 1 of 3: re-normalise with the fixed corrector (text_raw untouched)"
    & $py.Source "scripts/backfill_normalized_text.py" --force
    if ($LASTEXITCODE -ne 0) { Write-Err2 "backfill failed"; exit 1 }

    Write-Info "step 2 of 3: re-classify layout on the cleaner text"
    & $py.Source "scripts/classify_layout.py" --apply

    Write-Info "step 3 of 3: retrain dictionary, phrases and entities"
    Get-ChildItem "storage\learning\*.json" -ErrorAction SilentlyContinue | ForEach-Object {
        $d = Join-Path $bkDir "storage-learning"
        New-Item -ItemType Directory -Force -Path $d | Out-Null
        Move-Item $_.FullName -Destination $d -Force
    }
    & $py.Source "scripts/train_learning.py"
    if ($LASTEXITCODE -eq 0) { Write-Ok "rebuild complete" }
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
    Write-Host "  git add -A ; git commit -m 'fix: batch 7 - narrator name repair, clean display and phrases'" -ForegroundColor Gray
} else {
    Write-Warn2 "Mixed or regressed. Send me the comparison."
    Write-Host "  Revert:  Copy-Item -Recurse -Force '$bkDir\*' ." -ForegroundColor Yellow
}
Write-Host ""
exit $code
