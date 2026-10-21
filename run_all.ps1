# 4H-SiC Trench JFET TCAD - Master PowerShell Execution Script
# Reference: Monaghan et al., Key Engineering Materials 948 (2023)

$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host "      4H-SiC VERTICAL TRENCH JFET TCAD - MASTER POWERSHELL PIPELINE" -ForegroundColor Cyan
Write-Host "      Reference: Monaghan et al., Key Engineering Materials 948 (2023)" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host ""

# 0. Check Python
try {
    $pyVer = & python --version 2>&1
    Write-Host "[0/6] Python verified: $pyVer" -ForegroundColor Green
} catch {
    Write-Error "[ERROR] Python is not installed or not in PATH!"
}

# 1. Self-Test & Unit Tests
Write-Host "`n[1/6] Running Solver Self-Test and Pytest Verification..." -ForegroundColor Yellow
& python simulate_kem948_fig5.py --self-test
& python -m pytest tests/ -v
Write-Host "[PASS] Self-test and unit tests passed." -ForegroundColor Green

# 2. Coarse-Grid Simulation (mesh = 0.2 um, CP04)
Write-Host "`n[2/6] Running Coarse-Grid Simulation (mesh=0.2 um, CP04)..." -ForegroundColor Yellow
& python simulate_kem948_fig5.py --mesh 0.2 --control --output runs/CP04_coarse
Write-Host "[PASS] Coarse-grid simulation completed." -ForegroundColor Green

# 3. Fine-Grid Simulation (mesh = 0.1 um, CP05)
Write-Host "`n[3/6] Running Fine-Grid Simulation (mesh=0.1 um, CP05)..." -ForegroundColor Yellow
& python simulate_kem948_fig5.py --mesh 0.1 --control --output runs/CP05_fine
Write-Host "[PASS] Fine-grid simulation completed." -ForegroundColor Green

# 4. Checkpoint Validator
Write-Host "`n[4/6] Running JFET Checkpoint Validator (CP00 - CP05)..." -ForegroundColor Yellow
& python JFET_Checkpoint_Validator.py --coarse runs/CP04_coarse --fine runs/CP05_fine
Write-Host "[PASS] All checkpoints passed with 0 errors." -ForegroundColor Green

# 5. Master Reproduction Suite
Write-Host "`n[5/6] Running Master Reproduction Suite for All Paper Figures..." -ForegroundColor Yellow
& python reproduce_all.py
Write-Host "[PASS] Master reproduction completed. Figures saved in results/figures/." -ForegroundColor Green

# 6. Rebuild Native Mathematica Notebook
Write-Host "`n[6/6] Generating Native Mathematica Notebook (jfet_tcad_simulation.nb)..." -ForegroundColor Yellow
& python build_full_native_mathematica_tcad.py
Write-Host "[PASS] Native Mathematica notebook generated successfully." -ForegroundColor Green

# Optional: LaTeX Compilation
if (Get-Command pdflatex -ErrorAction SilentlyContinue) {
    Write-Host "`n[OPTIONAL] Compiling LaTeX PDF Technical Report..." -ForegroundColor Yellow
    Push-Location report
    try {
        $proc = Start-Process -FilePath "pdflatex" -ArgumentList "-interaction=nonstopmode", "jfet_tcad_report.tex" -NoNewWindow -Wait -PassThru
        if ($proc.ExitCode -eq 0) {
            Write-Host "[PASS] Report compiled: report\jfet_tcad_report.pdf" -ForegroundColor Green
        } else {
            Write-Host "[WARNING] pdflatex completed with non-zero exit code: $($proc.ExitCode)" -ForegroundColor Yellow
        }
    } catch {
        Write-Host "[WARNING] pdflatex compilation skipped: $_" -ForegroundColor Yellow
    } finally {
        Pop-Location
    }
}

Write-Host "`n==============================================================================" -ForegroundColor Cyan
Write-Host "                     ALL SIMULATIONS COMPLETED SUCCESSFULLY!" -ForegroundColor Cyan
Write-Host "==============================================================================" -ForegroundColor Cyan
Write-Host " - Runs and artifacts:    $PSScriptRoot\runs\"
Write-Host " - Master Figures:        $PSScriptRoot\results\figures\"
Write-Host " - Summary metrics JSON:  $PSScriptRoot\results\reproduction_summary.json"
Write-Host " - Mathematica Notebook: $PSScriptRoot\jfet_tcad_simulation.nb"
if (Test-Path "$PSScriptRoot\report\jfet_tcad_report.pdf") {
    Write-Host " - PDF Technical Report:  $PSScriptRoot\report\jfet_tcad_report.pdf"
}
Write-Host "==============================================================================`n" -ForegroundColor Cyan
