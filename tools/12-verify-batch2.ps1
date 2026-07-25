<#
.SYNOPSIS
  Verify batch 2 installation. Read-only.
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
        else { Write-Err2 $Name; $script:fail++; if ($Hint) { Write-Host "         -> $Hint" -ForegroundColor DarkGray } }
    } catch { Write-Err2 "$Name (error: $_)"; $script:fail++ }
}
$py = Get-Python

Write-Step "Modules installed"
Check "ocr_corrector.py"  { Test-Path "packages\ingestion\ocr_corrector.py" } ".\tools\10-install-batch2.ps1"
Check "fusion.py"         { Test-Path "packages\search\fusion.py" }           ".\tools\10-install-batch2.ps1"
Check "entity_filter.py"  { Test-Path "packages\learning\entity_filter.py" }  ".\tools\10-install-batch2.ps1"
Check "eval_search.py"    { Test-Path "scripts\eval_search.py" }              ".\tools\10-install-batch2.ps1"
Check "golden queries"    { Test-Path "datasets\golden\queries.jsonl" }       ".\tools\10-install-batch2.ps1"

Write-Step "Behaviour"
Check "batch 2 tests pass" {
    if (-not $py) { return "warn" }
    & $py.Source -m pytest "tests/unit/test_batch2.py" -q 2>&1 | Out-Null
    $LASTEXITCODE -eq 0
} ".\tools\10-install-batch2.ps1"

Check "batch 1 tests still pass (no regression)" {
    if (-not $py) { return "warn" }
    & $py.Source -m pytest "tests/unit/test_arabic_canonicalizer.py" -q 2>&1 | Out-Null
    $LASTEXITCODE -eq 0
} "investigate before continuing"

Check "OCR corrector repairs a known split" {
    if (-not $py) { return "warn" }
    $code = 'import sys;from packages.ingestion.ocr_corrector import Lexicon,OcrCorrector;' +
            'c=OcrCorrector(Lexicon("storage/learning/dictionary.json"));' +
            'o,_=c.correct(chr(1593)+" "+chr(1604)+chr(1610)+chr(1607));' +
            'sys.exit(0 if o.replace(" ","")==chr(1593)+chr(1604)+chr(1610)+chr(1607) else 1)'
    & $py.Source -c $code 2>&1 | Out-Null
    if ($LASTEXITCODE -eq 0) { return $true }
    return "warn"
} "needs storage/learning/dictionary.json - run training first"

Write-Step "Measurement gate"
Check "baseline captured" {
    if (Test-Path "_eval\baseline.json") { return $true }
    return "warn"
} ".\tools\11-baseline.ps1"

Write-Step "Result"
Write-Host ""
Write-Host "  passed  : $pass" -ForegroundColor Green
Write-Host "  warning : $warn" -ForegroundColor Yellow
Write-Host "  failed  : $fail" -ForegroundColor $(if ($fail -gt 0) { "Red" } else { "Gray" })
Write-Host ""
Write-Host "  Not wired yet (needs baseline numbers first):" -ForegroundColor Cyan
Write-Host "    - ranking.py -> use RRF instead of raw score addition" -ForegroundColor Gray
Write-Host "    - fts.py / fuzzy.py -> read text_normalized" -ForegroundColor Gray
Write-Host "    - service.py -> write text_raw + text_normalized on ingest" -ForegroundColor Gray
Write-Host "    - entities.py -> apply entity_filter" -ForegroundColor Gray
Write-Host ""
exit $(if ($fail -gt 0) { 1 } else { 0 })
