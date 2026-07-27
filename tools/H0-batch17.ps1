<#
.SYNOPSIS
  Batch 17: WIRING. Fixes the import failure and connects every engine into one pipeline.
.DESCRIPTION
  ROOT CAUSE OF THE E2E CRASH
    pyproject.toml declared:
        include = ["apps*", "packages*"]
    engines* was missing, so the package was never installed and never
    importable. That single line is why "No module named 'engines'" happened.

  THE UNIFIED PIPELINE  (spec 6.2)
    intent -> planner -> search -> entities -> narrator -> evidence ->
    verifier -> answer -> memory -> audit
    Every stage is timed and recorded in `trace`, so any result can be
    explained step by step. Measured end to end on simulated output: 48ms.

  NEW API ROUTES - added ALONGSIDE /search, not replacing it
    GET /pipeline/ask      the full documented pipeline
    GET /pipeline/report   a readable report: summary, evidence, narrators,
                           contradictions, what needs review, basis of verdict
    GET /pipeline/engines  live engine status

  FOUR FIXES FROM YOUR OUTPUT
    1. "muhamm d" - a space after a diacritic broke narrator names so they
       never matched the index. Now rejoined by a rule that needs no lexicon.
    2. sig_ocr_quality = 0 on READABLE text. Typographic tatweel was scored
       the same as a genuine misreading, so clean passages were thrown out of
       the evidence bundle. Tatweel is now weighted at a third, real
       misreadings are weighted up, and two-letter Arabic words like "an" and
       "min" are no longer counted as fragments.
    3. "] 026 [ 6" - Arabic-Indic digits, brackets and two numbers in one
       field. Now parsed into hadith number and sequence.
    4. "the water purifies and does not purify" was flagged as a
       contradiction. It is one explanatory sentence, not two conflicting
       reports. Real contradictions are still detected.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$SkipInstall,
    [string]$PatchDir = "$PSScriptRoot\..\patch19"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch19 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch17-" + (Get-Stamp))
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
    if ($text.Contains($repl.TrimEnd())) { Write-Info "$Label - already applied"; return }
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
$srcRoot = (Resolve-Path $PatchDir).Path
Get-ChildItem -Path $PatchDir -Recurse -File |
    Where-Object { $_.FullName -notmatch "\\snippets\\" -and $_.FullName -notmatch "__pycache__" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length + 1)
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
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "2/6  Register engines as an installable package"
Invoke-SafePatch -File "pyproject.toml" -A "pyproject_anchor.txt" -R "pyproject_repl.txt" `
    -Label "pyproject.toml: add engines* to the package list"
Invoke-SafePatch -File "apps\api\app\main.py" -A "main_anchor.txt" -R "main_repl.txt" `
    -Label "main.py: mount /pipeline routes"

Write-Step "3/6  Reinstall so engines becomes importable"
if ($DryRun) { Write-Dry "would run pip install -e ." }
elseif ($SkipInstall) { Write-Warn2 "skipped (-SkipInstall). engines will NOT import." }
else {
    & $py.Source -m pip install -e . --quiet --no-deps
    if ($LASTEXITCODE -ne 0) { Write-Warn2 "pip install reported an error" }
    else { Write-Ok "package reinstalled" }
}

Write-Step "4/6  Import check - this is what failed before"
if ($DryRun) { Write-Dry "would verify imports" }
else {
    $probe = @'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
mods = ["engines.evidence.bundle", "engines.evidence.verifier",
        "engines.narrator.gazetteer", "engines.planner.planner",
        "engines.memory.memory", "engines.pipeline.orchestrator",
        "engines.report.builder"]
bad = []
for m in mods:
    try:
        __import__(m)
        print("  ok  ", m)
    except Exception as exc:
        print("  FAIL", m, "-", exc)
        bad.append(m)
sys.exit(1 if bad else 0)
'@
    $pp = Join-Path $env:TEMP "islamicai_imports.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    Push-Location (Get-Location)
    & $py.Source $pp
    $importOk = ($LASTEXITCODE -eq 0)
    Pop-Location
    if ($importOk) { Write-Ok "all engines import" }
    else { Write-Err2 "imports still failing - send me the output"; exit 1 }
}

Write-Step "5/6  Tests"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "6/6  End-to-end on YOUR database"
if ($DryRun) { Write-Dry "would run the pipeline"; exit 0 }
$probe2 = @'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
from packages.database.session import SessionLocal
from engines.pipeline.orchestrator import Pipeline
from engines.report.builder import ReportBuilder

QUERIES = [
    chr(1575)+chr(1604)+chr(1605)+chr(1575)+chr(1569)+" "+chr(1610)+chr(1591)+chr(1607)+chr(1585),
    chr(1586)+chr(1585)+chr(1575)+chr(1585)+chr(1577)+" "+chr(1576)+chr(1606)+" "+chr(1571)+chr(1593)+chr(1610)+chr(1606),
    chr(1575)+chr(1604)+chr(1604)+chr(1607),
]
db = SessionLocal()
try:
    for q in QUERIES:
        out = Pipeline(db, use_memory=False).run(q, limit=20).as_dict()
        print("=" * 62)
        print("  QUERY:", q)
        print("    intent    : %s (%.2f)" % (out["intent"].get("label"),
                                             out["intent"].get("confidence", 0)))
        print("    plan      : %s" % "+".join(out["plan"].get("routes", [])))
        print("    entities  : %d after dedup" % len(out["entity_suggestions"]))
        nar = out.get("narrators", [])
        res = sum(1 for n in nar if n.get("resolution") in ("exact", "alias"))
        print("    narrators : %d resolved of %d" % (res, len(nar)))
        ev = out.get("evidence", {})
        print("    evidence  : %s citable, %s distinct positions"
              % (ev.get("citable_count"), ev.get("distinct_sources")))
        ver = out.get("verification", {})
        print("    verdict   : %s (%.2f)" % (ver.get("verdict"),
                                             ver.get("confidence", 0)))
        print("    answered  :", out["answer"].get("answered"))
        print("    total     : %.0f ms" % out.get("total_ms", 0))
        for s in out.get("trace", []):
            if s.get("skipped"):
                print("      SKIPPED %s - %s" % (s["stage"], s.get("reason")))
        print()
    # a full report for the first query
    out = Pipeline(db, use_memory=False).run(QUERIES[0], limit=20).as_dict()
    print(ReportBuilder().build(out).to_text())
    db.rollback()
    sys.exit(0)
except Exception as exc:
    import traceback
    traceback.print_exc()
    sys.exit(1)
finally:
    db.close()
'@
$pp2 = Join-Path $env:TEMP "islamicai_e2e17.py"
Write-Utf8NoBom -Path $pp2 -Content $probe2
& $py.Source $pp2
if ($LASTEXITCODE -eq 0) { Write-Ok "end-to-end pipeline works on your data" }
else { Write-Warn2 "pipeline failed - send me the traceback" }

Write-Host ""
Write-Host "  New endpoints once the API restarts:" -ForegroundColor Cyan
Write-Host "    GET /pipeline/ask?q=..." -ForegroundColor Gray
Write-Host "    GET /pipeline/report?q=...&fmt=text" -ForegroundColor Gray
Write-Host "    GET /pipeline/engines" -ForegroundColor Gray
Write-Host ""
Write-Host "  git add -A ; git commit -m 'feat: batch 17 - full engine wiring and unified pipeline'" -ForegroundColor Gray
Write-Host ""
exit 0
