@echo off
if "%~1"=="" echo Drag PNG files or folders onto this .bat && pause && exit /b
echo Checking for C2PA metadata...
python "%~dp0stripper.py" %* --dry-run
echo.
echo -----------------------------------------------
set /p CONFIRM="Confirm strip? (y/N): "
if /i "%CONFIRM%"=="y" (echo. && python "%~dp0stripper.py" %*) else (echo Cancelled.)
pause
