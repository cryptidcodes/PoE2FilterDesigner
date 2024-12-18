@echo off
echo Installing POE2 Filter Designer...

REM Check if Python is installed (try both python and py commands)
python --version >nul 2>&1
if errorlevel 1 (
    py --version >nul 2>&1
    if errorlevel 1 (
        echo Python is not installed or not in PATH! Please install Python 3.7 or later.
        echo You can download Python from: https://www.python.org/downloads/
        echo.
        echo IMPORTANT: During installation, make sure to check the box that says:
        echo "Add Python to PATH" or "Add Python to environment variables"
        pause
        exit /b 1
    )
)

REM Create required directories if they don't exist
if not exist "POE2FilterDesigner" mkdir POE2FilterDesigner
if not exist "POE2FilterDesigner\bases" mkdir POE2FilterDesigner\bases

REM Copy files to correct locations if they exist
if exist "poe2filter.py" copy "poe2filter.py" "POE2FilterDesigner\"
if exist "filterbase.filter" copy "filterbase.filter" "POE2FilterDesigner\"
if exist "filtersettings.txt" copy "filtersettings.txt" "POE2FilterDesigner\"

echo.
echo Installation complete!
echo Edit filtersettings.txt to customize your filter
echo Run run_filter.bat to generate your filter
echo.
pause
