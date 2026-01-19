$ErrorActionPreference = "Stop"

function Resolve-PythonCommand {
    $pyCmd = Get-Command py -ErrorAction SilentlyContinue
    if ($pyCmd) {
        return @("py", "-3")
    }
    $pythonCmd = Get-Command python -ErrorAction SilentlyContinue
    if ($pythonCmd) {
        return @("python")
    }
    throw "Python not found. Please install Python 3 and ensure it is on PATH."
}

$python = Resolve-PythonCommand

Write-Host "Creating venv..."
if ($python.Length -gt 1) {
    & $python[0] $python[1] -m venv .venv
} else {
    & $python[0] -m venv .venv
}

if (-not (Test-Path .\.venv\Scripts\python.exe)) {
    throw "Venv creation failed. .venv\\Scripts\\python.exe not found."
}

Write-Host "Installing dependencies..."
& .\.venv\Scripts\python.exe -m pip install -r backend\requirements.txt

Write-Host "Starting server..."
& .\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --app-dir backend
