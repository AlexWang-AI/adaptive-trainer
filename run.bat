@echo off
setlocal
cd /d "%~dp0"

if not exist ".env" (
    if exist ".env.example" (
        copy /Y ".env.example" ".env" >nul
        echo [INFO] .env was created from .env.example.
        echo [INFO] Edit .env and set a real OPENAI_API_KEY.
        echo.
    )
)

set "PYTHON_EXE=%USERPROFILE%\AppData\Local\Programs\Python\Python311\python.exe"
if not exist "%PYTHON_EXE%" (
    echo [ERROR] Python interpreter not found:
    echo   %PYTHON_EXE%
    echo Please install Python 3.11 at the path above.
    pause
    exit /b 1
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%~dp0"

echo.
echo ============================================
echo   AI Reverse Human Trainer
echo   Starting Streamlit...
echo   URL: http://localhost:8501
echo ============================================
echo.

start "" /b powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Start-Process 'http://localhost:8501'"

"%PYTHON_EXE%" -m streamlit run "ui/app.py" --server.headless true --server.address localhost --server.port 8501 --browser.gatherUsageStats false
set "EXIT_CODE=%ERRORLEVEL%"

echo.
if not "%EXIT_CODE%"=="0" (
    echo [ERROR] Streamlit failed to start. Exit code: %EXIT_CODE%
    echo Check the log above, the API key, and installed dependencies.
) else (
    echo Streamlit has exited.
)
pause
endlocal
