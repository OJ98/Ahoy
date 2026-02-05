# Demo 3 Harness Launcher - Concurrent Multiprotocol Execution
$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
$demoDir = Split-Path -Parent $scriptDir
$repoRoot = Split-Path -Parent $demoDir
Set-Location $repoRoot

Write-Host ""
Write-Host "========================================================================="
Write-Host "DEMO 3: Concurrent Multi-Protocol Participation"
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

python "$scriptDir\demo3_harness.py"

$exitCode = $LASTEXITCODE

if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "========================================================================="
    Write-Host "Demo 3 Harness completed successfully!"
    Write-Host "========================================================================="
    Write-Host ""
    Write-Host "Results saved to: $scriptDir\results\"
    Write-Host ""
} else {
    Write-Host ""
    Write-Host "========================================================================="
    Write-Host "Demo 3 Harness failed with exit code: $exitCode"
    Write-Host "========================================================================="
    Write-Host ""
}

exit $exitCode
