$ErrorActionPreference = 'Stop'
Push-Location -LiteralPath $PSScriptRoot
try {
    & '.\.venv\Scripts\python.exe' -m uvicorn quantum_primer.website:app --host 127.0.0.1 --port 8501
}
finally {
    Pop-Location
}
