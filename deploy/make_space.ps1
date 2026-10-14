# Assembles a folder you can push to a Hugging Face Space: the backend code, the Dockerfile and the Space README.
# Usage (from the repo root):   powershell -File deploy/make_space.ps1
# Output: build/space/   (gitignored)

$root = Split-Path -Parent $PSScriptRoot
$out = Join-Path $root "build\space"
if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force $out | Out-Null

foreach ($dir in "app", "data_sources", "rag", "vision") {
    robocopy (Join-Path $root "backend\$dir") (Join-Path $out $dir) /E /XD __pycache__ /XF *.pyc /NFL /NDL /NJH /NJS | Out-Null
}
Copy-Item (Join-Path $root "backend\pyproject.toml"), (Join-Path $root "backend\uv.lock") $out
Copy-Item (Join-Path $PSScriptRoot "Dockerfile") $out
Copy-Item (Join-Path $PSScriptRoot "space-README.md") (Join-Path $out "README.md")

"Space folder ready: $out"
Get-ChildItem $out | Select-Object Name
