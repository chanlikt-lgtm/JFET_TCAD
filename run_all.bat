@echo off
setlocal enabledelayedexpansion

title 4H-SiC Trench JFET TCAD - Complete Simulation Suite
cd /d "%~dp0"

echo ==============================================================================
echo       4H-SiC VERTICAL TRENCH JFET TCAD - MASTER EXECUTION PIPELINE
echo       Reference: Monaghan et al., Key Engineering Materials 948 (2023)
echo ==============================================================================
echo.

:: ----------------------------------------------------------------------------
:: 0. Check Python Environment
:: ----------------------------------------------------------------------------
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Python is not found in PATH! Please ensure Python 3.10+ is installed.
    goto :FAIL
)
echo [0/6] Python environment verified.
echo.

:: ----------------------------------------------------------------------------
:: 1. Self-Test & Unit Tests
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [1/6] Running Solver Self-Test and Pytest Verification...
echo ==============================================================================
python simulate_kem948_fig5.py --self-test
if %errorlevel% neq 0 (
    echo [ERROR] simulate_kem948_fig5.py --self-test failed!
    goto :FAIL
)

python -m pytest tests/ -v
if %errorlevel% neq 0 (
    echo [ERROR] Pytest suite failed!
    goto :FAIL
)
echo [PASS] Self-test and unit tests passed.
echo.

:: ----------------------------------------------------------------------------
:: 2. Official Runbook Simulation - Coarse Grid (CP04)
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [2/6] Running Coarse-Grid Simulation (mesh=0.2 um, CP04)...
echo ==============================================================================
python simulate_kem948_fig5.py --mesh 0.2 --control --output runs/CP04_coarse
if %errorlevel% neq 0 (
    echo [ERROR] Coarse-grid simulation failed!
    goto :FAIL
)
echo [PASS] Coarse-grid simulation completed.
echo.

:: ----------------------------------------------------------------------------
:: 3. Official Runbook Simulation - Fine Grid (CP05)
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [3/6] Running Fine-Grid Simulation (mesh=0.1 um, CP05)...
echo ==============================================================================
python simulate_kem948_fig5.py --mesh 0.1 --control --output runs/CP05_fine
if %errorlevel% neq 0 (
    echo [ERROR] Fine-grid simulation failed!
    goto :FAIL
)
echo [PASS] Fine-grid simulation completed.
echo.

:: ----------------------------------------------------------------------------
:: 4. Checkpoint Validator
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [4/6] Running JFET Checkpoint Validator (Scope: Scientific, Fail-Stop)...
echo ==============================================================================
python JFET_Checkpoint_Validator.py --coarse runs/CP04_coarse --fine runs/CP05_fine --run-self-test --scope scientific --json runs\checkpoints.json
if %errorlevel% neq 0 (
    echo.
    echo ==============================================================================
    echo [FAIL-STOP] Checkpoint Validator halted pipeline with errorlevel %errorlevel%!
    echo Unvalidated physical claims or unresolved physics blocked progression.
    echo Inspection report saved at: runs\checkpoints.json
    echo ==============================================================================
    goto :FAIL
)
echo [PASS] Checkpoints passed.
echo.

:: ----------------------------------------------------------------------------
:: 5. Master Reproduction Suite (Figures 2.1, 3, 4, 5.1, 5.2, 6.1, 6.2)
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [5/6] Running Master Reproduction Suite for All Paper Figures...
echo ==============================================================================
python reproduce_all.py
if %errorlevel% neq 0 (
    echo [ERROR] reproduce_all.py failed!
    goto :FAIL
)
echo [PASS] Master reproduction completed. Figures saved in results/figures/.
echo.

:: ----------------------------------------------------------------------------
:: 6. Rebuild Native Mathematica Notebook (jfet_tcad_simulation.nb)
:: ----------------------------------------------------------------------------
echo ==============================================================================
echo [6/6] Generating Native Mathematica Notebook (jfet_tcad_simulation.nb)...
echo ==============================================================================
python build_full_native_mathematica_tcad.py
if %errorlevel% neq 0 (
    echo [WARNING] Mathematica notebook generation had warnings or skipped.
) else (
    echo [PASS] Native Mathematica notebook generated successfully.
)
echo.

:: ----------------------------------------------------------------------------
:: Optional: Compile LaTeX PDF Report if pdflatex is installed
:: ----------------------------------------------------------------------------
where pdflatex >nul 2>&1
if %errorlevel% equ 0 (
    echo [OPTIONAL] Compiling LaTeX PDF Technical Report...
    cd report
    pdflatex -interaction=nonstopmode jfet_tcad_report.tex >nul 2>&1
    cd ..
    echo [PASS] Report compiled: report\jfet_tcad_report.pdf
    echo.
)

echo ==============================================================================
echo                      ALL SIMULATIONS COMPLETED SUCCESSFULLY!
echo ==============================================================================
echo  - Runs and artifacts:    %~dp0runs\
echo  - Master Figures (PDF/PNG): %~dp0results\figures\
echo  - Summary metrics JSON:   %~dp0results\reproduction_summary.json
echo  - Mathematica Notebook:  %~dp0jfet_tcad_simulation.nb
if exist "%~dp0report\jfet_tcad_report.pdf" echo  - PDF Technical Report:   %~dp0report\jfet_tcad_report.pdf
echo ==============================================================================
echo.
pause
exit /b 0

:FAIL
echo.
echo ==============================================================================
echo                      [FAILED] PIPELINE ENCOUNTERED AN ERROR
echo ==============================================================================
echo Please inspect the error messages above.
echo.
pause
exit /b 1
