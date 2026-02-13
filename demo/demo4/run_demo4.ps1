# Demo 4: Custom Events Integration
# Runs agents with external event injection

param(
    [switch]$Clean = $false
)

# Get script directory
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = Split-Path -Parent (Split-Path -Parent $ScriptDir)

Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host "DEMO 4: Custom Events Integration" -ForegroundColor Cyan
Write-Host "======================================================================" -ForegroundColor Cyan
Write-Host ""

# Check conda environment
Write-Host "Checking conda environment..." -ForegroundColor Yellow
conda env list | Select-String "maf-py" > $null
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: maf-py conda environment not found" -ForegroundColor Red
    Write-Host "Create it with: conda env create -f environment.yml" -ForegroundColor Yellow
    exit 1
}

# Activate environment
Write-Host "Activating maf-py environment..." -ForegroundColor Yellow
conda activate maf-py
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to activate maf-py environment" -ForegroundColor Red
    exit 1
}

# Clean state if requested
if ($Clean) {
    Write-Host "Cleaning previous state..." -ForegroundColor Yellow
    Remove-Item -Path "$env:TEMP\maf_*" -ErrorAction SilentlyContinue
    Remove-Item -Path "$ProjectRoot\logs\agent_notes\agent_notes.json" -ErrorAction SilentlyContinue
}

# Create results directory
$ResultsDir = "$ScriptDir\results"
New-Item -ItemType Directory -Path $ResultsDir -Force > $null

Write-Host "Results directory: $ResultsDir" -ForegroundColor Cyan
Write-Host ""

# Run demo harness
Write-Host "Starting Demo 4 harness..." -ForegroundColor Yellow
Write-Host "NOTE: This may take 1-2 minutes as it runs agents and injects events" -ForegroundColor Yellow
Write-Host ""

cd $ProjectRoot
python "$ScriptDir\demo4_harness.py"

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "DEMO 4 COMPLETED SUCCESSFULLY" -ForegroundColor Green
    Write-Host "======================================================================" -ForegroundColor Green
    Write-Host "Results saved to: $ResultsDir" -ForegroundColor Green
    Write-Host ""
    Write-Host "Files generated:" -ForegroundColor Cyan
    Get-ChildItem -Path $ResultsDir -File -Name | ForEach-Object { Write-Host "  - $_" }
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "DEMO 4 FAILED" -ForegroundColor Red
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "Check logs for details:" -ForegroundColor Yellow
    Get-ChildItem -Path "$ResultsDir\demo4_*.log" | Select-Object -First 1 | ForEach-Object {
        Write-Host "  $($_.FullName)"
    }
    exit 1
}
