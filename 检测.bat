@echo off
if "%~1"=="" echo Drag PNG files or folders onto this .bat && pause && exit /b
python "%~dp0detect.py" %* -v
pause
