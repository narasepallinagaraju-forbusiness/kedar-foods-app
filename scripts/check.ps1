$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$ruff = Join-Path $repoRoot "infra\.venv\Scripts\ruff.exe"
$mypy = Join-Path $repoRoot "infra\.venv\Scripts\mypy.exe"
$python = Join-Path $repoRoot "infra\.venv\Scripts\python.exe"
$config = Join-Path $repoRoot "pyproject.toml"

& $ruff check infra api scripts\seed --config $config
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $mypy --config-file $config infra\app.py infra\frontend_stack.py infra\backend_stack.py infra\tests api scripts\seed
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

& $python -m pytest -c $config -q
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}
