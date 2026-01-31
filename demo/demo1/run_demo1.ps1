# Demo 1 Harness Launcher
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$demoDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $demoDir
Set-Location $repoRoot

Write-Host ""
Write-Host "========================================================================="
Write-Host "DEMO 1: Sequential Multi-Protocol Execution Harness"
Write-Host "========================================================================="
Write-Host ""

Write-Host "Activating environment maf-py..."
$condaActivated = $false
try {
    conda activate maf-py 2>$null
    if ($?) {
        Write-Host " Activated conda environment maf-py"
        $condaActivated = $true
    }
} catch {
    # conda not available
}

if (-not $condaActivated) {
    Write-Host "Note: conda not available, attempting venv activation..."
    $venvPath = Join-Path $repoRoot "maf-py\Scripts\Activate.ps1"
    if (Test-Path $venvPath) {
        & $venvPath
        Write-Host " Activated venv"
    } else {
        Write-Host "Warning: Could not activate environment. Proceeding anyway..."
    }
}

Write-Host ""
Write-Host "Starting demo harness..."
Write-Host ""

python "$scriptDir\demo1_harness.py"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "========================================================================="
    Write-Host "Demo 1 Harness completed successfully!"
    Write-Host "========================================================================="
    Write-Host ""
    Write-Host "Results saved in: $scriptDir\results\"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================================================="
    Write-Host "Demo 1 Harness failed with exit code: $exitCode"
    Write-Host "========================================================================="
    Write-Host ""
}

exit $exitCode

