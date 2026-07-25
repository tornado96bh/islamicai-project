<#
.SYNOPSIS
  Verify every fix was actually applied. Read-only.
#>
[CmdletBinding()]
param()
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

$pass = 0; $fail = 0; $warn = 0
function Check {
    param($Name, [scriptblock]$Test, $Hint = "")
    try {
        $r = & $Test
        if ($r -eq $true)      { Write-Ok $Name;    $script:pass++ }
        elseif ($r -eq "warn") { Write-Warn2 $Name; $script:warn++ }
        else {
            Write-Err2 $Name; $script:fail++
            if ($Hint) { Write-Host "         -> $Hint" -ForegroundColor DarkGray }
        }
    } catch { Write-Err2 "$Name (error: $_)"; $script:fail++ }
}

Write-Step "Secrets"
Check ".env not tracked by git" { [string]::IsNullOrWhiteSpace((git ls-files -- .env)) } ".\tools\01-secrets.ps1"
Check ".env.bak removed" { -not (Test-Path ".env.bak") } ".\tools\01-secrets.ps1"
Check "postgres password is not a default" {
    if (-not (Test-Path .env)) { return $false }
    -not ((Read-Utf8 ".env") -match 'POSTGRES_PASSWORD=(change_me|changeme|password|123)')
} ".\tools\01-secrets.ps1"

Write-Step "Repo hygiene"
Check ".gitignore has more than 40 lines" {
    (Test-Path ".gitignore") -and ((Get-Content ".gitignore").Count -gt 40)
} ".\tools\02-purge.ps1"
Check "no derived data tracked under storage/" {
    [string]::IsNullOrWhiteSpace((git ls-files -- "storage/*"))
} ".\tools\02-purge.ps1"
Check "no .bak files tracked" { [string]::IsNullOrWhiteSpace((git ls-files -- "*.bak")) } ".\tools\02-purge.ps1"
Check "tracked size under 10 MB" {
    $s = 0
    git ls-files | ForEach-Object { if (Test-Path -LiteralPath $_) { $s += (Get-Item -LiteralPath $_).Length } }
    Write-Host ("         (current: " + [math]::Round($s/1MB,1) + " MB)") -ForegroundColor DarkGray
    $s -lt 10MB
} ".\tools\02-purge.ps1"

Write-Step "Guardrails"
Check "normalize_existing_text.py disabled" {
    if (-not (Test-Path "scripts\normalize_existing_text.py")) { return $true }
    (Read-Utf8 "scripts\normalize_existing_text.py") -match "sys\.exit"
} ".\tools\03-guardrails.ps1"
Check "no sync training in manager.py" {
    if (-not (Test-Path "packages\ingestion\manager.py")) { return $false }
    (Read-Utf8 "packages\ingestion\manager.py") -notmatch "trainer\.train_book"
} ".\tools\03-guardrails.ps1"
Check "trainer.py merges instead of overwriting" {
    if (-not (Test-Path "packages\learning\trainer.py")) { return $false }
    (Read-Utf8 "packages\learning\trainer.py") -match "_merge_profile_index"
} ".\tools\03-guardrails.ps1"

Write-Step "Canonicalizer"
Check "arabic_canonicalizer.py installed" { Test-Path "packages\utils\arabic_canonicalizer.py" } ".\tools\04-install-canonicalizer.ps1"
Check "old normalizers now re-export (no duplication)" {
    if (-not ((Test-Path "packages\utils\arabic_normalizer.py") -and (Test-Path "packages\learning\canonicalizer.py"))) { return $false }
    ((Read-Utf8 "packages\utils\arabic_normalizer.py") -match "arabic_canonicalizer") -and
    ((Read-Utf8 "packages\learning\canonicalizer.py") -match "arabic_canonicalizer")
} ".\tools\04-install-canonicalizer.ps1"

$py = Get-Python
Check "alef/hamza folding actually works" {
    if (-not $py) { return "warn" }
    $code = 'import sys;from packages.utils.arabic_canonicalizer import search_form_text as s;sys.exit(0 if s(chr(1573)+chr(1587)+chr(1605)+chr(1575)+chr(1593)+chr(1610)+chr(1604))==s(chr(1575)+chr(1587)+chr(1605)+chr(1575)+chr(1593)+chr(1610)+chr(1604)) else 1)'
    & $py.Source -c $code 2>&1 | Out-Null
    $LASTEXITCODE -eq 0
} ".\tools\04-install-canonicalizer.ps1"
Check "canonicalizer tests pass" {
    if (-not $py) { return "warn" }
    if (-not (Test-Path "tests\unit\test_arabic_canonicalizer.py")) { return $false }
    & $py.Source -m pytest "tests/unit/test_arabic_canonicalizer.py" -q 2>&1 | Out-Null
    $LASTEXITCODE -eq 0
} ".\tools\04-install-canonicalizer.ps1"

Write-Step "Database"
Check "migration file installed" {
    Test-Path "alembic\versions\a1b2c3d4e5f6_split_raw_normalized_and_fix_indexes.py"
} ".\tools\05-migrations.ps1"
Check "safe backfill script installed" { Test-Path "scripts\backfill_normalized_text.py" } ".\tools\04-install-canonicalizer.ps1"
Check "new indexes exist in the database" {
    $docker = Get-Command docker -ErrorAction SilentlyContinue
    if (-not $docker) { return "warn" }
    $running = docker ps --filter "name=islamicai_postgres" --format "{{.Names}}" 2>$null
    if ([string]::IsNullOrWhiteSpace($running)) { return "warn" }
    $u = "islamicai"; $d = "islamicai"
    if (Test-Path .env) {
        $t = Read-Utf8 ".env"
        if ($t -match 'POSTGRES_USER=(.+)') { $u = $Matches[1].Trim() }
        if ($t -match 'POSTGRES_DB=(.+)')   { $d = $Matches[1].Trim() }
    }
    $q = "SELECT count(*) FROM pg_indexes WHERE indexname IN ('ix_page_elements_norm_fts','ix_page_elements_norm_trgm');"
    $out = docker exec islamicai_postgres psql -U $u -d $d -tAc $q 2>$null
    ([int]$out) -eq 2
} ".\tools\05-migrations.ps1 -Apply"

Write-Step "Result"
Write-Host ""
Write-Host "  passed  : $pass" -ForegroundColor Green
Write-Host "  warning : $warn" -ForegroundColor Yellow
Write-Host "  failed  : $fail" -ForegroundColor $(if ($fail -gt 0) { "Red" } else { "Gray" })
Write-Host ""
if ($fail -eq 0) { Write-Host "  All applicable checks passed." -ForegroundColor Green }
else { Write-Host "  Review the failed items above." -ForegroundColor Red }
Write-Host ""
Write-Host "  Still open (batch 2):" -ForegroundColor Cyan
Write-Host "    - point fts.py / fuzzy.py at text_normalized" -ForegroundColor Gray
Write-Host "    - RRF fusion instead of raw score addition" -ForegroundColor Gray
Write-Host "    - replace the fake 256-dim hash EmbeddingBuilder" -ForegroundColor Gray
Write-Host "    - golden dataset + eval harness" -ForegroundColor Gray
Write-Host ""
exit $(if ($fail -gt 0) { 1 } else { 0 })
