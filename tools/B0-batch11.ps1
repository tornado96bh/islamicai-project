<#
.SYNOPSIS
  Batch 11: fix the two stale tests I shipped, and unblock the real bottleneck.
.DESCRIPTION
  Two things.

  1. I shipped batch 10 with batch 9's test file still in place. Two of its
     assertions encode the OLD design (ocr_quality as a reward) and now fail.
     An expected-failing test is worse than no test - it erodes trust in the
     whole suite. Updated with the reason written into the file.

  2. The real bottleneck. Twice in this project the measurement lied:
       - a hidden latency regression, because the comparison was against the
         ORIGINAL baseline instead of the previous run
       - a quality regression that RAISED must_contain_rate to 0.875, because
         every boilerplate line contains the query word
     Both trace to five golden questions and one weak metric. Recall@k and MRR
     are disabled because relevant_element_ids is empty, and nobody but you can
     fill it.

     scripts/build_golden.py reduces your work to: look at ten results, type
     the numbers of the correct ones, press Enter. Twenty questions is about
     an hour. It suggests queries derived from YOUR corpus - narrator names and
     phrases the system actually learned - and saves after every judgement.

     eval_search.py now also compares against the PREVIOUS run, so a gradual
     regression cannot hide behind a distant baseline again.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [int]$Suggest = 0,
    [string]$PatchDir = "$PSScriptRoot\..\patch13"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch13 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch11-" + (Get-Stamp))

Write-Step "1/4  Install files"
$files = @(
  @{ p = "tests\unit\test_signals.py";  n = "updated for the 1.1.0 design" },
  @{ p = "scripts\build_golden.py";     n = "interactive golden set builder" },
  @{ p = "scripts\eval_search.py";      n = "also compares against the previous run" }
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

Write-Step "2/4  Full test suite - expect zero failures now"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m py_compile "scripts\build_golden.py" 2>&1 | Out-Null
    if ($LASTEXITCODE -ne 0) { Write-Err2 "SYNTAX ERROR in build_golden.py"; exit 1 }
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass - no expected failures left" }
    else { Write-Err2 "still failing - send me the output" }
}

Write-Step "3/4  Golden set status"
if ($DryRun) { Write-Dry "would show status" }
else { & $py.Source "scripts/build_golden.py" --status }

Write-Step "4/4  Build the golden set"
if ($DryRun) { Write-Dry "would start the judging session"; exit 0 }
if ($Suggest -gt 0) {
    Write-Info "starting a judging session with $Suggest suggested queries"
    Write-Warn2 "For each query: look at the ten results, type the numbers of"
    Write-Warn2 "the CORRECT ones, press Enter. 's' skips, 'q' saves and quits."
    Write-Warn2 "Your work is saved after every single judgement."
    Write-Host ""
    & $py.Source "scripts/build_golden.py" --suggest $Suggest
} else {
    Write-Host ""
    Write-Host "  To start judging (about an hour for twenty questions):" -ForegroundColor Cyan
    Write-Host "    .\tools\B0-batch11.ps1 -Suggest 25" -ForegroundColor Gray
    Write-Host "  or a single query of your own:" -ForegroundColor Cyan
    Write-Host "    python scripts/build_golden.py --query `"...`" --intent entity" -ForegroundColor Gray
    Write-Host ""
    Write-Host "  Once twenty are judged, Recall@k and MRR switch on and the" -ForegroundColor Yellow
    Write-Host "  measurement stops depending on must_contain_rate alone." -ForegroundColor Yellow
    Write-Host ""
}
exit 0
