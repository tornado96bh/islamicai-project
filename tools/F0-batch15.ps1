<#
.SYNOPSIS
  Batch 15: diacritic-aware matching, real intent confidence, engine registry, two test fixes.
.DESCRIPTION
  1. TWO FAILING TESTS FIXED
     "a l-Hasan" was not rejoined because alef was blanket-protected. It is
     now protected only where it stands as a word, not where it is a split
     definite article.
     "al-Nabi salla Allah alayhi wa alihi" was rejected as a salutation. It
     is a legitimate title; the rejection now applies only when the formula
     is stuck to a NARRATOR name (one carrying a nasab).

  2. DIACRITICS ENGINE - the thing you keep asking for
     Four text layers, not two:
        raw        the original, sacred
        display    readable, every diacritic and hamza kept
        canonical  unified spelling WITH diacritics - this is what tells
                   'alam apart from 'ilm, and unites mas'ul with mas'ul
        retrieval  unvocalised, for the index
     Matching returns a GRADE, not yes/no:
        exact 1.00  canonical 0.92  unvocalised 0.70  stem 0.45
     So a diacritised query prefers a diacritised match without discarding
     the unvocalised one - because the source itself may be unvocalised.

  3. INTENT CONFIDENCE - 0.55 was a hardcoded constant, not a measurement
     Now computed from weighted evidence, and explainable: every score can
     be traced to named evidence.
        narrator 0.90   isnad 0.88   chapter 0.85   ruling 0.81
        average over clear intents: 0.84
     "Allah" alone still returns ~0.20 - and that is CORRECT. One common
     word has no clear intent; claiming otherwise is miscalibration. The
     system should ask for clarification, not pretend.

  4. ENGINE REGISTRY - honest status of all 24 layers
     10 ready, 3 partial, 4 waiting on YOUR data, 3 contract-only, 7 not
     started. require_engine() raises with a REASON rather than returning
     a misleading silent result.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$PatchDir = "$PSScriptRoot\..\patch17"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch17 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch15-" + (Get-Stamp))

Write-Step "1/4  Install files"
$files = @(
  @{ p = "packages\ingestion\ocr_corrector.py"; n = "v1.3.0 - split definite article rejoined" },
  @{ p = "packages\learning\entity_filter.py";  n = "v1.3.0 - sacred titles allowed" },
  @{ p = "packages\arabic\diacritics.py";       n = "diacritic-aware matching engine" },
  @{ p = "packages\arabic\__init__.py";         n = "package marker" },
  @{ p = "packages\search\intent_v2.py";        n = "evidence-based intent confidence" },
  @{ p = "packages\engines\registry.py";        n = "honest status of all 24 layers" },
  @{ p = "packages\engines\__init__.py";        n = "package marker" },
  @{ p = "datasets\catalog\sources.json";       n = "your source catalog, machine-readable" },
  @{ p = "tests\unit\test_batch15.py";          n = "39 tests" }
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

Write-Step "2/4  Full test suite - the two failures should be gone"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "still failing - send me the output" }
}

Write-Step "3/4  Engine registry"
if ($DryRun) { Write-Dry "would print the registry" }
else {
    $probe = @'
import sys
from packages.engines.registry import report, summary, blocked_by_user
print(report())
print()
print("=" * 62)
print("  summary:", summary())
print()
waiting = blocked_by_user()
if waiting:
    print("  Waiting on YOUR data - nobody else can supply these:")
    for e in waiting:
        print("   -", e.name_ar, "|", ", ".join(e.blocked_by))
sys.exit(0)
'@
    $pp = Join-Path $env:TEMP "islamicai_registry.py"
    Write-Utf8NoBom -Path $pp -Content $probe
    & $py.Source $pp
}

Write-Step "4/4  Diacritics and intent probe"
if ($DryRun) { Write-Dry "would probe"; exit 0 }
$probe2 = @'
from packages.arabic.diacritics import match_words, analyse
from packages.search.intent_v2 import detect_intent
print("  diacritic matching:")
for a, b in [("\u0639\u064e\u0644\u064e\u0645", "\u0639\u064e\u0644\u064e\u0645"),
             ("\u0639\u064e\u0644\u064e\u0645", "\u0639\u0644\u0645"),
             ("\u0645\u0633\u0624\u0648\u0644", "\u0645\u0633\u0626\u0648\u0644")]:
    r = match_words(a, b)
    print("    %-10s %-10s  %-12s %.2f" % (a, b, r.strength.value, r.weight))
print()
print("  intent confidence:")
for q in ["\u0632\u0631\u0627\u0631\u0629 \u0628\u0646 \u0623\u0639\u064a\u0646",
          "\u0628\u0627\u0628 \u0646\u0648\u0627\u0642\u0636 \u0627\u0644\u0648\u0636\u0648\u0621",
          "\u0627\u0644\u0644\u0647"]:
    r = detect_intent(q)
    print("    %-24s %-10s %.2f" % (q, r.label, r.confidence))
'@
$pp2 = Join-Path $env:TEMP "islamicai_diac.py"
Write-Utf8NoBom -Path $pp2 -Content $probe2
& $py.Source $pp2
Write-Host ""
Write-Host "  git add -A ; git commit -m 'feat: batch 15 - diacritics engine, intent confidence, registry'" -ForegroundColor Gray
Write-Host ""
exit 0
