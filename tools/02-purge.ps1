<#
.SYNOPSIS
  Untrack ~79MB of derived data, .bak files and dumps. Writes a real .gitignore.
#>
[CmdletBinding()]
param([switch]$DryRun, [switch]$DeleteBakFiles)
. "$PSScriptRoot\_common.ps1"
Assert-RepoRoot

Write-Step "1/4  Measure tracked size"
$before = 0
git ls-files | ForEach-Object {
    if (Test-Path -LiteralPath $_) { $before += (Get-Item -LiteralPath $_).Length }
}
Write-Info ("tracked size now: " + [math]::Round($before/1MB,1) + " MB")

Write-Step "2/4  Untrack derived data and junk"
$derived = @(
  "storage/learning/phrases.json", "storage/learning/context.json",
  "storage/learning/dictionary.json", "storage/learning/entities.json",
  "storage/learning/page_embeddings.json", "storage/learning/book_embeddings.json",
  "storage/learning/training_summary.json"
)
$junk = @(
  "*.bak", "production_audit.py.fixbak", "production_audit.py.before_datetime_fix",
  "production_audit.py.before_import_fix", "production_audit.py.before_settings_fix",
  "islamicai_search_final_pack.zip", "project_tree.txt", "project_source_dump.txt",
  "architecture_dump.txt", "api_tree.txt", "packages_tree.txt", "manifest.json",
  "error.txt", "book.txt", "edition.txt", "sample.pdf",
  "tests/Wasael-Shia-part01.pdf", "islamicai.egg-info"
)
$removed = 0
Write-Info "-- derived layers --"
foreach ($p in $derived) { $removed += (Remove-FromGitIndex -PathSpec $p -DryRun:$DryRun) }
Write-Info "-- development junk --"
foreach ($p in $junk)    { $removed += (Remove-FromGitIndex -PathSpec $p -DryRun:$DryRun) }
Write-Ok "total untracked: $removed file(s)"

if ($DeleteBakFiles) {
    $baks = Get-ChildItem -Recurse -File -Include "*.bak","*.fixbak","*.before_*_fix" -ErrorAction SilentlyContinue |
            Where-Object { $_.FullName -notmatch "\\\.git\\" -and $_.FullName -notmatch "\\_backup\\" }
    if ($DryRun) { Write-Dry ("would delete " + $baks.Count + " .bak file(s) from disk") }
    elseif ($baks.Count -gt 0) { $baks | Remove-Item -Force; Write-Ok ("deleted " + $baks.Count + " .bak file(s)") }
} else { Write-Info ".bak files kept on disk. Use -DeleteBakFiles to remove them." }

Write-Step "3/4  Write .gitignore"
$gi = @"
# IslamicAI .gitignore
# Rule: never commit a derived layer that can be rebuilt (master spec 5)

# secrets
.env
.env.*
!.env.example
*.pem
*.key

# python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
build/
dist/
.venv/
venv/
env/
.pytest_cache/
.ruff_cache/
.mypy_cache/
.coverage
htmlcov/

# derived layers - rebuilt from PostgreSQL
storage/
data/storage/
data/cache/
data/tmp/
data/logs/
*.faiss
*.index

# backups and junk
*.bak
*.fixbak
*.before_*_fix
*.orig
*.rej
*~
_backup/

# dumps and diagnostics
project_tree.txt
project_source_dump.txt
architecture_dump.txt
api_tree.txt
packages_tree.txt
error.txt

# heavy files belong in MinIO or data/, not git
*.zip
*.tar.gz
*.7z
*.pdf
*.djvu
*.epub
*.pt
*.bin
*.onnx
*.safetensors

# small test fixtures are allowed
!tests/fixtures/**

# os and editors
Thumbs.db
desktop.ini
.DS_Store
.vscode/
.idea/
"@
if ($DryRun) { Write-Dry "would write .gitignore" }
else { Write-Utf8NoBom -Path ".gitignore" -Content $gi; Write-Ok ("wrote .gitignore - " + ($gi -split "`n").Count + " lines (was 6)") }

Write-Step "4/4  Note on git history"
Write-Warn2 "Files are untracked but still exist in git history."
Write-Warn2 "Clone size will not shrink until history is rewritten:"
Write-Host "    pip install git-filter-repo" -ForegroundColor Gray
Write-Host "    git filter-repo --strip-blobs-bigger-than 1M --force" -ForegroundColor Gray
Write-Warn2 "That rewrites every commit and needs a force-push. Backup first."
Write-Host ""
