<#
.SYNOPSIS
  Stop three data-destroying behaviours found during the audit.
.DESCRIPTION
  1) scripts/normalize_existing_text.py overwrites the original text in place.
  2) packages/ingestion/manager.py runs heavy training inside the import path.
  3) packages/learning/trainer.py rewrites page_embeddings.json completely,
     wiping vectors of every previously imported book.
  Each edit verifies its anchor matches EXACTLY ONCE, otherwise it aborts.
  All Arabic replacement text lives in patch\snippets\ and is read as UTF-8.
#>
[CmdletBinding()]
param([switch]$DryRun, [string]$PatchDir = "$PSScriptRoot\..\patch")
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

$snip = Join-Path $PatchDir "snippets"
if (-not (Test-Path -LiteralPath $snip)) { throw "snippets folder not found: $snip" }

function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    $t = [System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))
    return $t -replace "`r`n", "`n"
}

function Invoke-SafePatch {
    param([string]$File, [string]$Anchor, [string]$Replacement, [string]$Label, [switch]$DryRun)
    if (-not (Test-Path -LiteralPath $File)) { Write-Warn2 "$Label - file missing: $File"; return $false }

    $orig = Read-Utf8 $File
    $text = $orig -replace "`r`n", "`n"

    if ($Replacement.Length -gt 40 -and $text.Contains($Replacement.TrimEnd())) {
        Write-Info "$Label - already applied, skipping"; return $true
    }
    $i = $text.IndexOf($Anchor)
    if ($i -lt 0) { Write-Err2 "$Label - anchor NOT found. Nothing changed."; return $false }
    if ($text.IndexOf($Anchor, $i + 1) -ge 0) { Write-Err2 "$Label - anchor found more than once. Aborted."; return $false }
    if ($DryRun) { Write-Dry "$Label - would apply"; return $true }

    Write-Utf8NoBom -Path $File -Content ($text.Replace($Anchor, $Replacement))
    Write-Ok "$Label - applied"
    return $true
}

Write-Step "1/3  Disable normalize_existing_text.py"
if (Test-Path "scripts\normalize_existing_text.py") {
    if ($DryRun) { Write-Dry "would replace it with a guarded stub" }
    else {
        Write-Utf8NoBom -Path "scripts\normalize_existing_text.py" -Content (Get-Snippet "normalize_guard.py")
        Write-Ok "normalize_existing_text.py now exits immediately with an explanation"
    }
} else { Write-Info "file not present" }

Write-Step "2/3  Remove synchronous training from the import path"
Invoke-SafePatch -File "packages\ingestion\manager.py" `
    -Anchor (Get-Snippet "manager_anchor.txt") -Replacement (Get-Snippet "manager_repl.txt") `
    -Label "manager.py: drop sync train_book" -DryRun:$DryRun | Out-Null

Write-Step "3/3  Merge instead of overwrite in trainer.py"
$okA = Invoke-SafePatch -File "packages\learning\trainer.py" `
    -Anchor (Get-Snippet "trainer_page_anchor.txt") -Replacement (Get-Snippet "trainer_page_repl.txt") `
    -Label "trainer.py: page index merge" -DryRun:$DryRun
$okB = Invoke-SafePatch -File "packages\learning\trainer.py" `
    -Anchor (Get-Snippet "trainer_book_anchor.txt") -Replacement (Get-Snippet "trainer_book_repl.txt") `
    -Label "trainer.py: book index merge" -DryRun:$DryRun

if (($okA -or $okB) -and -not $DryRun) {
    $tp = "packages\learning\trainer.py"
    $tt = Read-Utf8 $tp
    if ($tt -notmatch "def _merge_profile_index") {
        Write-Utf8NoBom -Path $tp -Content ($tt.TrimEnd() + "`n" + (Get-Snippet "trainer_helper.txt") + "`n")
        Write-Ok "added _merge_profile_index() to trainer.py"
    } else { Write-Info "merge helper already present" }
}

Write-Step "Syntax check"
$py = Get-Python
if (-not $py) { Write-Warn2 "python not found - skipping syntax check" }
elseif ($DryRun) { Write-Dry "would run py_compile" }
else {
    foreach ($f in @("packages\learning\trainer.py","packages\ingestion\manager.py","scripts\normalize_existing_text.py")) {
        if (Test-Path $f) {
            & $py.Source -m py_compile $f 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok "syntax ok: $f" } else { Write-Err2 "SYNTAX ERROR in $f - review now" }
        }
    }
}
Write-Host ""
Write-Ok "Guardrails installed."
Write-Host ""
