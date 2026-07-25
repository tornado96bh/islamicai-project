<#
.SYNOPSIS
  Install the unified Arabic canonicalizer and remove the duplicate normalizers.
#>
[CmdletBinding()]
param([switch]$DryRun, [string]$PatchDir = "$PSScriptRoot\..\patch")
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch folder not found: $PatchDir" }

Write-Step "1/4  Copy patch files"
$files = @(
  @{ p = "packages\utils\arabic_canonicalizer.py";      n = "unified canonicalizer + offset map" },
  @{ p = "packages\utils\arabic_normalizer.py";         n = "compat re-export" },
  @{ p = "packages\learning\canonicalizer.py";          n = "compat re-export" },
  @{ p = "packages\database\models\page_element.py";    n = "text_raw / text_normalized columns" },
  @{ p = "scripts\backfill_normalized_text.py";         n = "safe replacement for the destructive script" },
  @{ p = "tests\unit\test_arabic_canonicalizer.py";     n = "32 tests" }
)
$bkDir = Join-Path "_backup" ("replaced-" + (Get-Stamp))
foreach ($f in $files) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Err2 ("patch file missing: " + $f.p); continue }
    if ($DryRun) { Write-Dry ($f.p + "  - " + $f.n); continue }
    if (Test-Path -LiteralPath $f.p) {
        $bk = Join-Path $bkDir $f.p
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $f.p -Destination $bk -Force
    }
    $d = Split-Path -Parent $f.p
    if ($d -and -not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
    $content = [System.IO.File]::ReadAllText([System.IO.Path]::GetFullPath($src),
               (New-Object System.Text.UTF8Encoding($false)))
    Write-Utf8NoBom -Path $f.p -Content $content
    Write-Ok ($f.p + "  - " + $f.n)
}

Write-Step "2/4  Ensure __init__.py files"
foreach ($d in @("packages\utils", "tests\unit")) {
    $init = Join-Path $d "__init__.py"
    if ((Test-Path -LiteralPath $d) -and -not (Test-Path -LiteralPath $init)) {
        if ($DryRun) { Write-Dry "would create $init" }
        else { Write-Utf8NoBom -Path $init -Content ""; Write-Ok "created $init" }
    }
}

Write-Step "3/4  Syntax check"
$py = Get-Python
if (-not $py) { Write-Warn2 "python not found - skipping" }
elseif ($DryRun) { Write-Dry "would run py_compile and pytest" }
else {
    foreach ($f in $files) {
        if (Test-Path -LiteralPath $f.p) {
            & $py.Source -m py_compile $f.p 2>&1 | Out-Null
            if ($LASTEXITCODE -eq 0) { Write-Ok ("syntax ok: " + $f.p) } else { Write-Err2 ("SYNTAX ERROR: " + $f.p) }
        }
    }
}

Write-Step "4/4  Run canonicalizer tests"
if ($py -and -not $DryRun) {
    & $py.Source -m pytest "tests/unit/test_arabic_canonicalizer.py" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all canonicalizer tests passed" }
    else {
        Write-Err2 "tests failed - review output above"
        Write-Warn2 "to revert: git checkout -- packages/ scripts/ tests/"
    }
}
Write-Host ""
Write-Host "  Next:  .\tools\05-migrations.ps1" -ForegroundColor Cyan
Write-Host ""
