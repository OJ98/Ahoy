@echo off
REM Ablation Study Launcher for Windows
REM This script activates the maf-py conda environment and runs the ablation study

setlocal enabledelayedexpansion

echo ======================================================================
echo ABLATION STUDY LAUNCHER
echo ======================================================================

REM Check if conda is available
where conda >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: conda command not found. Please install Miniconda/Anaconda.
    pause
    exit /b 1
)

REM Try to activate maf-py environment
echo.
echo Activating maf-py environment...
call conda activate maf-py 2>nul

REM Verify activation
python -c "import sys; print('✓ Environment: ' + sys.executable)" >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: Failed to activate maf-py environment
    echo Please run: conda create -f environment.yml -n maf-py
    pause
    exit /b 1
)

REM Navigate to project root
cd /d "%~dp0.."

REM Run verification
echo.
echo Running setup verification...
python ablation/verify_setup.py
if %ERRORLEVEL% NEQ 0 (
    echo Setup verification failed!
    pause
    exit /b 1
)

REM Run ablation study harness with arguments
echo.
echo Running ablation study harness...
python ablation/run_ablation.py %*

pause
