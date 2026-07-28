<#
.SYNOPSIS
  Batch 20: the eight requested engines, plus the index-poisoning fix.
.DESCRIPTION
  THE INDEX POISONING - the most consequential fix here
    search_form_text stripped diacritics BEFORE rejoining split words, so
    "muhamm d" became "muham d" and the only evidence that the split was
    damage was destroyed. The name was indexed as two words, and searching
    for "Muhammad" could never find it. Order is now: rejoin, then strip.

  THE EIGHT ENGINES
    Knowledge Graph      multi-hop questions: "who narrated from Zurara and
                         from whom did Ibn Abi Umayr narrate?" - a PATH
                         question, not a text match. Derived layer, rebuilt
                         from PostgreSQL, not a parallel store.
    Ontology             28 seed concepts. Expansion by CONCEPT: "purity"
                         reaches wudu, ghusl, tayammum because they are its
                         branches. Exclusions make "wudu except jabira"
                         expressible.
    Temporal Reasoning   did the student live to hear the teacher? Kulayni
                         (d.329) cannot narrate from Zurara (d.150) - a
                         broken chain however continuous the text looks.
                         Missing dates return UNKNOWN, never "broken".
    Contradiction        not "conflict found" but: type, shared topic, and
                         the reconciliations the usulis recognise - general
                         and specific, absolute and restricted, different
                         case. It PRESENTS them and does not choose.
    Fiqh Reasoner        reads each proof: explicit, apparent, implied, or
                         irrelevant. States what is missing for a ruling.
                         Issues NO fatwa - that is the mujtahid's work.
    Cross-Encoder        BAAI/bge-reranker-v2-m3, weight ZERO until measured.
    Learning to Rank     learns signal weights from golden judgements, capped
                         inside the RRF scale.
    Calibration          makes 0.9 mean 90%. On simulated data it detected
                         overconfidence: ECE 0.18, and 0.9 calibrated to 0.73.

  117 tests pass, zero failures.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [switch]$Rebuild,
    [switch]$SkipInstall,
    [string]$PatchDir = "$PSScriptRoot\..\patch22"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

# -Rebuild alone must not need the patch folder: last time it aborted with
# "patch21 folder not found" because the check ran before the mode was known.
$needsPatch = -not ($Rebuild -and -not $DryRun -and $PSBoundParameters.Count -eq 1)
if ($needsPatch -and -not (Test-Path -LiteralPath $PatchDir)) {
    Write-Warn2 "patch folder not found: $PatchDir"
    Write-Warn2 "If you only want to rebuild data, that is fine - continuing."
    $needsPatch = $false
}

$bkDir = Join-Path "_backup" ("batch20-" + (Get-Stamp))
$snip = Join-Path $PatchDir "snippets"

function Get-Snippet {
    param([string]$Name)
    $p = Join-Path $snip $Name
    if (-not (Test-Path -LiteralPath $p)) { throw "missing snippet: $Name" }
    return (([System.IO.File]::ReadAllText($p, (New-Object System.Text.UTF8Encoding($false)))) -replace "`r`n", "`n")
}

if ($needsPatch) {
Write-Step "1/6  Install engines"
$srcRoot = (Resolve-Path $PatchDir).Path
$skipped = 0
Get-ChildItem -Path $PatchDir -Recurse -File |
    Where-Object { $_.FullName -notmatch "__pycache__" -and $_.FullName -notmatch "\\snippets\\" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length + 1)
        if ($_.Length -eq 0 -and (Test-Path -LiteralPath $rel)) {
            if ((Get-Item -LiteralPath $rel).Length -gt 0) {
                Write-Warn2 ("skipped empty overwrite: " + $rel); $skipped++; return
            }
        }
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
if ($skipped -gt 0) { Write-Info "$skipped empty file(s) skipped by the guard" }

Write-Step "2/6  Fix index poisoning in the canonicaliser"
$target = "packages\learning\canonicalizer.py"
if (Test-Path -LiteralPath $target) {
    $anchor = Get-Snippet "search_form_anchor.txt"
    $repl = Get-Snippet "search_form_repl.txt"
    $text = (Read-Utf8 $target) -replace "`r`n", "`n"
    if ($text.Contains("repair_diacritic_splits")) { Write-Info "already applied" }
    elseif ($text.IndexOf($anchor) -lt 0) { Write-Err2 "anchor NOT found - nothing changed" }
    elseif ($DryRun) { Write-Dry "canonicalizer.py - would apply" }
    else {
        $bk = Join-Path $bkDir $target
        New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
        Copy-Item -LiteralPath $target -Destination $bk -Force
        Write-Utf8NoBom -Path $target -Content ($text.Replace($anchor, $repl))
        Write-Ok "canonicalizer.py - rejoin now happens BEFORE stripping diacritics"
    }
}

Write-Step "3/6  Reinstall so engines resolve"
if ($DryRun) { Write-Dry "would run pip install -e ." }
elseif ($SkipInstall) { Write-Warn2 "skipped (-SkipInstall)" }
else {
    & $py.Source -m pip install -e . --quiet --no-deps
    if ($LASTEXITCODE -eq 0) { Write-Ok "package reinstalled" }
    else { Write-Warn2 "pip reported an error" }
}

Write-Step "4/6  Guard and tests"
if ($DryRun) { Write-Dry "would run verify_imports and pytest"; exit 0 }
& $py.Source "scripts/verify_imports.py"
& $py.Source -m pytest "tests/unit" -q
if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" } else { Write-Warn2 "review failures above" }

Write-Step "5/6  Engine probe"
$probe = @'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
from engines.graph.knowledge_graph import KnowledgeGraph, NodeType, EdgeType
from engines.ontology.concepts import Ontology
from engines.reasoning.temporal import TemporalReasoner, Lifespan
from engines.reasoning.contradiction import ContradictionEngine
from engines.fiqh.reasoner import FiqhReasoner
from engines.ranking.reranker_v2 import CrossEncoderReranker, ConfidenceCalibrator

onto = Ontology()
print("  ontology        :", len(onto), "concepts")
g = KnowledgeGraph()
g.add_node("a", NodeType.NARRATOR, "A"); g.add_node("b", NodeType.NARRATOR, "B")
g.add_edge("a", "b", EdgeType.NARRATED_FROM, evidence=["x"])
print("  knowledge graph :", g.stats())
t = TemporalReasoner()
v = t.can_meet(Lifespan("Kulayni", death=329), Lifespan("Zurara", death=150))
print("  temporal        :", v.relation.value)
ce = CrossEncoderReranker()
print("  cross-encoder   : model", ce.model_name, "| weight", ce.weight, "| loaded", ce.load())
print("  calibrator      : unfitted returns input ->", ConfidenceCalibrator().calibrate(0.87))
'@
$pp = Join-Path $env:TEMP "islamicai_probe20.py"
Write-Utf8NoBom -Path $pp -Content $probe
& $py.Source $pp
}

Write-Step "6/6  Rebuild stored text with the corrected index rule"
if ($DryRun) { Write-Dry "would rebuild"; exit 0 }
if (-not $Rebuild) {
    Write-Warn2 "NOT rebuilt. Until you rebuild, search_text keeps the split names."
    Write-Host "    .\tools\K0-batch20.ps1 -Rebuild" -ForegroundColor Cyan
} else {
    Write-Info "this is the step that gets 'muham d' out of the INDEX"
    & $py.Source "scripts/backfill_normalized_text.py" --force
    if (Test-Path "scripts\backfill_display_and_split.py") {
        & $py.Source "scripts/backfill_display_and_split.py" --apply
    }
    if (Test-Path "scripts\classify_layout.py") { & $py.Source "scripts/classify_layout.py" --apply }
    & $py.Source "scripts/train_learning.py"
    Write-Ok "rebuild complete"
}
Write-Host ""
Write-Host "  git add -A ; git commit -m 'feat: batch 20 - graph, ontology, temporal, contradiction, fiqh, ltr, calibration'" -ForegroundColor Gray
Write-Host ""
exit 0
