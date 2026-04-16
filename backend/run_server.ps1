$python = "d:\New_Project\AI_Project\MoneyAPP\.venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "Python virtual environment not found at $python"
    exit 1
}

& $python -m uvicorn backend.app.main:app --host 0.0.0.0 --port 8000
