<#
.SYNOPSIS
  Batch 16: the Master Spec engines - Evidence, Verifier, FinalAnswer, Narrator, Planner, Memory, Governance.
.DESCRIPTION
  Built directly against IslamicAI_Final_Master_Spec.docx sections 6.2, 8 and 9.

  EVIDENCE -> VERIFIER -> FINAL ANSWER  (spec 6.2)
    The move from "search engine" to "documentation platform". A result is no
    longer a list of hits but a bundle where every piece carries its exact
    position, and the verifier REFUSES to answer when evidence is thin.
    Spec section 2: "no guessing when evidence is insufficient".
    Measured on a simulation of your own output:
       2 independent citable sources -> answerable, confidence 0.92
       1 weak source, unclear intent -> refused, with the reasons listed

  NARRATOR ENGINE  (spec 8)
    A 30-narrator seed gazetteer of the major transmitters, with resolution by
    exact name, alias, kunya, or fuzzy. Unknown names are DECLARED unresolved,
    never assigned an invented id. Extend by editing the JSON, not the code.
    10 of 11 names from your own output now resolve.

  PLANNER ENGINE  (spec 8)
    Semantic search on the single word "Allah" returned 60 results that were
    all discarded - pure wasted time. The plan is now chosen from the intent:
    narrator -> lexical + gazetteer, concept -> semantic first, one common
    word -> cheapest route plus a request for clarification.

  MEMORY ENGINE  (spec 8, 9 Safe Learning)
    Stores only VERIFIED results, and invalidates automatically when any
    pipeline version changes - a result built by an older corrector is no
    longer valid. This is what separates it from a cache.

  GOVERNANCE  (spec 9)
    RBAC with four roles, an append-only audit log where every decision
    carries actor and reason, and circuit breakers enforcing time, result
    and expansion budgets.

  Plus two fixes from your output: ", 'an Ibn Abi Umayr" as an entity, and
  "Ahmad b. Muhammad" appearing twice with split frequencies.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$PatchDir = "$PSScriptRoot\..\patch18"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch18 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch16-" + (Get-Stamp))

Write-Step "1/4  Install engines"
$files = @(
  @{ p = "engines\__init__.py";                    n = "engines package" },
  @{ p = "engines\evidence\__init__.py";           n = "" },
  @{ p = "engines\evidence\bundle.py";             n = "Evidence Engine - spec 6.2" },
  @{ p = "engines\evidence\verifier.py";           n = "Verifier + FinalAnswer - spec 6.2" },
  @{ p = "engines\narrator\__init__.py";           n = "" },
  @{ p = "engines\narrator\gazetteer.py";          n = "Narrator Engine - spec 8" },
  @{ p = "engines\planner\__init__.py";            n = "" },
  @{ p = "engines\planner\planner.py";             n = "Planner Engine - spec 8" },
  @{ p = "engines\memory\__init__.py";             n = "" },
  @{ p = "engines\memory\memory.py";               n = "Memory Engine - spec 8" },
  @{ p = "packages\governance\__init__.py";        n = "" },
  @{ p = "packages\governance\audit.py";           n = "RBAC + Audit + Circuit Breakers - spec 9" },
  @{ p = "packages\learning\entity_filter.py";     n = "v1.4.0 - boundary sanitiser" },
  @{ p = "packages\learning\entity_dedup.py";      n = "entity deduplication" },
  @{ p = "datasets\gazetteer\narrators.json";      n = "30 seed narrators - extend this file" },
  @{ p = "tests\unit\test_batch16.py";             n = "42 tests" }
)
foreach ($f in $files) {
    $src = Join-Path $PatchDir $f.p
    if (-not (Test-Path -LiteralPath $src)) { Write-Warn2 ("missing: " + $f.p); continue }
    if ($DryRun) { Write-Dry ($f.p + $(if ($f.n) { "  - " + $f.n } else { "" })); continue }
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
    if ($f.n) { Write-Ok ($f.p + "  - " + $f.n) }
}
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "2/4  Full test suite"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "3/4  End-to-end: search -> evidence -> verify -> answer"
if ($DryRun) { Write-Dry "would run the pipeline on a real query" }
else {
    $probe = @'
import sys
from packages.database.session import SessionLocal
from packages.search.engine import SearchEngine
from engines.evidence.bundle import EvidenceBuilder
from engines.evidence.verifier import Verifier, compose
from engines.planner.planner import Planner
from engines.narrator.gazetteer import NarratorGazetteer

QUERIES = [
    chr(1575)+chr(1604)+chr(1604)+chr(1607),
    chr(1586)+chr(1585)+chr(1575)+chr(1585)+chr(1577)+" "+chr(1576)+chr(1606)+" "+chr(1571)+chr(1593)+chr(1610)+chr(1606),
]
db = SessionLocal()
try:
    gaz = NarratorGazetteer()
    print("  gazetteer loaded :", len(gaz), "narrators")
    print()
    engine = SearchEngine(db)
    for q in QUERIES:
        payload = engine.search(q, limit=20)
        intent = payload.get("intent", {})
        plan = Planner().plan(q, intent.get("label", "general"),
                              float(intent.get("confidence", 0) or 0))
        bundle = EvidenceBuilder().build(payload)
        result = Verifier().verify(bundle)
        answer = compose(bundle, result)
        print("  QUERY:", q)
        print("    plan          :", "+".join(r.value for r in plan.routes))
        if plan.ask_clarification:
            print("    clarification :", plan.clarification)
        print("    evidence      : %d citable of %d, %d distinct positions"
              % (len(bundle.citable), len(bundle.items), bundle.distinct_sources))
        print("    verdict       : %s  (confidence %.2f)"
              % (result.verdict.value, result.confidence))
        print("    answered      :", answer.answered)
        if answer.answered:
            for c in answer.citations[:3]:
                print("      -", c["citation"], "|", (c["text"] or "")[:52])
        else:
            print("    refused       :", answer.refusal_reason[:110])
        print()
    db.rollback()
    sys.exit(0)
except Exception as exc:
    print("  FAILED:", exc)
    sys.exit(1)
finally:
    db.close()
'@
    $pp = Join-Path $env:TEMP "islamicai_e2e.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
    if ($LASTEXITCODE -eq 0) { Write-Ok "end-to-end pipeline runs" }
    else { Write-Warn2 "pipeline failed - send me the output" }
}

Write-Step "4/4  Engine registry"
if ($DryRun) { Write-Dry "would print the registry"; exit 0 }
Write-Host ""
Write-Host "  The engines are built and tested but NOT yet wired into the API." -ForegroundColor Yellow
Write-Host "  They run standalone so you can inspect each one before it changes" -ForegroundColor Yellow
Write-Host "  search behaviour. Wiring is the next batch, after you see the output." -ForegroundColor Yellow
Write-Host ""
Write-Host "  To extend the narrator gazetteer - data, not code:" -ForegroundColor Cyan
Write-Host "    datasets\gazetteer\narrators.json" -ForegroundColor Gray
Write-Host ""
Write-Host "  git add -A ; git commit -m 'feat: batch 16 - evidence, verifier, narrator, planner, memory, governance'" -ForegroundColor Gray
Write-Host ""
exit 0
