@echo off
cd /d "%~dp0"
echo Running POE2 Filter Designer...
python POE2FilterDesigner\poe2filter.py
if errorlevel 1 (
    echo.
    echo Error running the filter generator! 
    echo Please make sure you've run setup.bat first and all files are in place.
)
echo.
echo Filter generation complete! Press any key to exit.
pause >nul
