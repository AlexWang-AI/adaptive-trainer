param(
    [ValidateSet("check", "demo", "test", "eval", "api", "mutate")]
    [string]$Task = "check"
)

$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

$PY = $env:STARTER_KIT_PYTHON
if (-not $PY) {
    $candidate = Join-Path $env:USERPROFILE "Desktop\deeptutor_env\Scripts\python.exe"
    if (Test-Path $candidate) {
        $PY = $candidate
    } elseif (Get-Command python -ErrorAction SilentlyContinue) {
        $PY = "python"
    } else {
        $PY = "py"
    }
}

Write-Host "Python: $PY" -ForegroundColor Cyan
switch ($Task) {
    "check"  { & $PY 00_env_check.py }
    "demo"   { & $PY demo.py }
    "mutate" { & $PY demo.py --mutate }
    "test"   { & $PY -m pytest tests -q }
    "eval"   { & $PY eval_passk.py --k 3 }
    "api"    { & $PY -m uvicorn api:app --host 127.0.0.1 --port 8010 }
}
