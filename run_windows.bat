@echo off
setlocal
cd /d "%~dp0"
set STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

if not exist ".venv\Scripts\python.exe" (
    echo Creating the private local Python environment...
    python -m venv .venv
    if errorlevel 1 (
        echo Python 3 is required. Install Python from https://www.python.org/downloads/windows/
        pause
        exit /b 1
    )
)

if not exist ".venv\.installed" (
    echo Installing required packages...
    .venv\Scripts\python.exe -m pip install -r requirements.txt
    if errorlevel 1 (
        echo Dependency installation failed. Check your internet connection and try again.
        pause
        exit /b 1
    )
    type nul > ".venv\.installed"
)

echo Starting Data Quality Studio...
start "Data Quality Studio" /b ".venv\Scripts\python.exe" -m streamlit run app.py --server.address 127.0.0.1 --server.headless true

echo Waiting for the local app to start...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$deadline=(Get-Date).AddSeconds(60); $ready=$false; do { $ready=(Test-NetConnection -ComputerName 127.0.0.1 -Port 8501 -InformationLevel Quiet -WarningAction SilentlyContinue); if (-not $ready) { Start-Sleep -Milliseconds 500 } } while (-not $ready -and (Get-Date) -lt $deadline); if ($ready) { Start-Process 'http://127.0.0.1:8501' } else { Write-Host 'The app did not start within 60 seconds.'; exit 1 }"
if errorlevel 1 (
    echo Could not start Data Quality Studio. Check the Python or Streamlit output.
    pause
    exit /b 1
)

echo Data Quality Studio is open at http://127.0.0.1:8501
echo Close the Streamlit process from Task Manager when you are finished.
pause
