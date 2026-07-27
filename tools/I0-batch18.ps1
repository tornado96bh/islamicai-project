<#
.SYNOPSIS
  Batch 18: repair the import failure I caused in batch 17.
.DESCRIPTION
  WHAT BROKE AND WHY - this was my mistake

    Batch 17 shipped __init__.py files that I created with `touch` purely as
    package markers. They were EMPTY. The installer copies every file in the
    patch recursively, so those empty files OVERWROTE the real lazy-import
    modules built in batch 14.

    The result:
        ImportError: cannot import name 'BookImportResult' from
        'packages.ingestion'

    An empty __init__.py is syntactically valid, so nothing complained until
    the server tried to start.

  THE REPAIR
    1. The three lazy-import modules are restored:
         packages/ingestion/__init__.py
         packages/search/__init__.py
         packages/learning/__init__.py
    2. They now report the REAL cause on failure. Previously a missing
       dependency surfaced as "cannot import name X" - so you would look for
       X, find it present, and never see that the actual problem was a
       missing driver three modules deeper.
    3. scripts/verify_imports.py is a guard: it fails loudly if any of those
       files is empty again, and it checks every name the routers actually
       import. Run it before starting the server.

  This installer refuses to copy an empty file over a non-empty one, so the
  same class of accident cannot repeat.
#>
[CmdletBinding()]
param(
    [switch]$DryRun,
    [string]$PatchDir = "$PSScriptRoot\..\patch20"
)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot
if (-not (Test-Path -LiteralPath $PatchDir)) { throw "patch20 folder not found: $PatchDir" }
$py = Get-Python
if (-not $py) { Write-Err2 "python not found"; exit 1 }

$bkDir = Join-Path "_backup" ("batch18-" + (Get-Stamp))

Write-Step "1/4  Restore the lazy-import modules"
$srcRoot = (Resolve-Path $PatchDir).Path
$skipped = 0
Get-ChildItem -Path $PatchDir -Recurse -File |
    Where-Object { $_.FullName -notmatch "__pycache__" } |
    ForEach-Object {
        $rel = $_.FullName.Substring($srcRoot.Length + 1)

        # GUARD: never let an empty file replace a real one.
        # This is exactly what broke the server last time.
        if ($_.Length -eq 0 -and (Test-Path -LiteralPath $rel)) {
            $existing = (Get-Item -LiteralPath $rel).Length
            if ($existing -gt 0) {
                Write-Warn2 ("skipped empty overwrite: " + $rel)
                $skipped++
                return
            }
        }

        if ($DryRun) { Write-Dry ($rel + "  (" + $_.Length + " bytes)"); return }
        if (Test-Path -LiteralPath $rel) {
            $bk = Join-Path $bkDir $rel
            New-Item -ItemType Directory -Force -Path (Split-Path -Parent $bk) | Out-Null
            Copy-Item -LiteralPath $rel -Destination $bk -Force
        }
        $d = Split-Path -Parent $rel
        if ($d -and -not (Test-Path -LiteralPath $d)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }
        $c = [System.IO.File]::ReadAllText($_.FullName, (New-Object System.Text.UTF8Encoding($false)))
        Write-Utf8NoBom -Path $rel -Content $c
        Write-Ok ($rel + "  (" + $_.Length + " bytes)")
    }
if ($skipped -gt 0) { Write-Info ("$skipped empty file(s) skipped by the guard") }
if (-not $DryRun) { Write-Info ("originals saved in " + $bkDir) }

Write-Step "2/4  Import guard - this is what would have caught the breakage"
if ($DryRun) { Write-Dry "would run scripts/verify_imports.py" }
else {
    & $py.Source "scripts/verify_imports.py"
    $guard = $LASTEXITCODE
    if ($guard -eq 0) { Write-Ok "every import the routers need resolves" }
    else { Write-Err2 "imports still broken - the output above names the cause" }
}

Write-Step "3/4  Tests"
if ($DryRun) { Write-Dry "would run pytest" }
else {
    & $py.Source -m pytest "tests/unit" -q
    if ($LASTEXITCODE -eq 0) { Write-Ok "all tests pass" }
    else { Write-Warn2 "some tests failed - review above" }
}

Write-Step "4/4  Server start check"
if ($DryRun) { Write-Dry "would import the FastAPI app"; exit 0 }
$probe = @'
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd()))
try:
    from apps.api.app.main import app
    routes = sorted({r.path for r in app.routes})
    print("  app imported OK -", len(routes), "routes")
    for r in routes:
        print("   ", r)
    has_pipeline = any(r.startswith("/pipeline") for r in routes)
    print()
    print("  /pipeline mounted :", has_pipeline)
    if not has_pipeline:
        print("  (engines not installed - run: pip install -e .)")
    sys.exit(0)
except Exception as exc:
    import traceback
    traceback.print_exc()
    sys.exit(1)
'@
$pp = Join-Path $env:TEMP "islamicai_appcheck.py"
Write-Utf8NoBom -Path $pp -Content $probe
& $py.Source $pp
if ($LASTEXITCODE -eq 0) {
    Write-Ok "the FastAPI app imports - uvicorn will start"
    Write-Host ""
    Write-Host "    uvicorn apps.api.app.main:app --reload" -ForegroundColor Cyan
} else {
    Write-Err2 "the app still fails to import - send me the traceback above"
}
Write-Host ""
Write-Host "  Run the guard before every start:" -ForegroundColor Gray
Write-Host "    python scripts/verify_imports.py" -ForegroundColor Gray
Write-Host ""
Write-Host "  git add -A ; git commit -m 'fix: batch 18 - restore lazy imports, add import guard'" -ForegroundColor Gray
Write-Host ""
exit 0
