# Multi-Agent Framework Startup Script
# Features:
#   - Activates `maf-py` (conda), falls back to common venv locations.
#   - Runs CHIPS interface to configure protocol/role(s) if needed
#   - [NEW] Supports multi-role mode: ahoy can now claim multiple roles across different protocols
#   - Starts agent scripts as background jobs with consolidated logging: ./logs/agents.log
#   - Dynamically skips agents whose roles are claimed by ahoy (prevents port conflicts)
#   - Waits for completion signal or keypress, then gracefully shuts down all agents

$ErrorActionPreference = 'Stop'

# Ensure script runs from repository root (where this file lives)
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Definition
Set-Location $scriptDir

# Try to activate conda env; if not available, try common venv locations.
Write-Host "Activating environment 'maf-py' if available..."
try {
	# This will succeed only if conda is initialized in PowerShell
	conda activate maf-py 2>$null
} catch {
	Write-Host "conda activate failed or not available. Trying local venv activations..."
	if (Test-Path (Join-Path $scriptDir "maf-py\Scripts\Activate.ps1")) {
		& (Join-Path $scriptDir "maf-py\Scripts\Activate.ps1")
	} elseif (Test-Path (Join-Path $scriptDir ".venv\Scripts\Activate.ps1")) {
		& (Join-Path $scriptDir ".venv\Scripts\Activate.ps1")
	} else {
		Write-Host "No local activation script found. Continuing without explicit activation. Ensure 'maf-py' is active if required."
	}
}

# Check if CHIPS config already exists
$chipsConfigFile = Join-Path $env:TEMP "maf_chips_config.txt"
$configExists = Test-Path $chipsConfigFile

# Run CHIPS if config doesn't exist or user wants to reconfigure
if (-not $configExists) {
	Write-Host ""
	Write-Host "No CHIPS configuration found. Running CHIPS interface..."
	Write-Host ""
	
	python chips.py
	
	if (-not (Test-Path $chipsConfigFile)) {
		Write-Host "Error: CHIPS configuration not created. Exiting."
		exit 1
	}
} else {
	Write-Host ""
	Write-Host "CHIPS configuration found: $chipsConfigFile"
	$currentConfig = Get-Content -Path $chipsConfigFile
	Write-Host "Current config: $currentConfig"
	Write-Host ""
	
	$reconfigure = Read-Host "Reconfigure? (yes/no) [default: no]"
	if ($reconfigure -eq "yes" -or $reconfigure -eq "y") {
		Write-Host ""
		python chips.py
		
		if (-not (Test-Path $chipsConfigFile)) {
			Write-Host "Error: CHIPS configuration not created. Exiting."
			exit 1
		}
	}
}

# Prepare logging
$logDir = Join-Path $scriptDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "agents.log"

# Parse CHIPS config and set MULTIPROTOCOL_AHOY_ROLES environment variable
# This ensures ALL agents (including Seller) load with correct address routing from the start
Write-Host "Parsing CHIPS configuration to set routing..."
$chipsConfig = Get-Content -Path $chipsConfigFile
try {
	# Try parsing as JSON (multi-role format)
	$configObj = $chipsConfig | ConvertFrom-Json
	if ($configObj.roles) {
		# Multi-role format: extract all roles
		$rolesStr = ($configObj.roles | ForEach-Object { "$($_.protocol):$($_.role)" }) -join ','
		Write-Host "  Multi-role detected: $rolesStr"
		$env:MULTIPROTOCOL_AHOY_ROLES = $rolesStr
	}
} catch {
	# Try simple "Protocol:Role" format (backward compatible)
	if ($chipsConfig -match '^[^:]+:[^:]+$') {
		Write-Host "  Single-role format: $chipsConfig"
		$env:MULTIPROTOCOL_AHOY_ROLES = $chipsConfig
	} else {
		Write-Host "  Warning: Could not parse CHIPS config format"
	}
}

if ($env:MULTIPROTOCOL_AHOY_ROLES) {
	Write-Host "  MULTIPROTOCOL_AHOY_ROLES=$($env:MULTIPROTOCOL_AHOY_ROLES)"
} else {
	Write-Host "  (No environment variable set)"
}

# Detect Python executable - try conda environment first, then system python
function Get-PythonExecutable {
	if (Get-Command python -ErrorAction SilentlyContinue) {
		return (Get-Command python).Source
	}
	if (Get-Command python3 -ErrorAction SilentlyContinue) {
		return (Get-Command python3).Source
	}
	# Fallback to default conda env path
	return "C:\\Users\\Omkar\\miniconda3\\envs\\maf-py\\python.exe"
}
$pythonExe = Get-PythonExecutable
if (-not (Test-Path $pythonExe)) {
	Write-Host "Warning: Python executable not found at $pythonExe. Continuing anyway..."
}

# List of agent scripts to start
$allAgents = @("agents/ahoy.py", "agents/buyer.py", "agents/seller.py", "agents/shipper.py", "agents/merchant.py", "agents/packer.py", "agents/labeler.py", "agents/wrapper.py", "agents/credit_buyer.py", "agents/credit_seller.py", "agents/credit_shipper.py", "agents/flexible_customer.py", "agents/flexible_merchant.py")

# Mapping of agent files to their protocol and role
$agentRoles = @{
	"agents/buyer.py" = "Purchase:Buyer"
	"agents/seller.py" = "Purchase:Seller"
	"agents/shipper.py" = "Purchase:Shipper"
	"agents/credit_buyer.py" = "CreditPurchase:CreditBuyer"
	"agents/credit_seller.py" = "CreditPurchase:CreditSeller"
	"agents/credit_shipper.py" = "CreditPurchase:CreditShipper"
	"agents/merchant.py" = "Logistics:Merchant"
	"agents/packer.py" = "Logistics:Packer"
	"agents/labeler.py" = "Logistics:Labeler"
	"agents/wrapper.py" = "Logistics:Wrapper"
	"agents/flexible_customer.py" = "FlexiblePurchase:FlexibleCustomer"
	"agents/flexible_merchant.py" = "FlexiblePurchase:FlexibleMerchant"
}

# Initialize array to track started processes
$startedProcs = @()

# Initialize claimed roles list (will be populated by ahoy)
$claimedRoles = @()

# Clean up old claimed role file
$claimedRoleFile = Join-Path $env:TEMP "maf_claimed_role_$($proc.Id).txt"

# Start ahoy first to determine which role it will claim
Write-Host "Starting ahoy first to determine claimed role..."

# Determine which ahoy script to run
# Priority: MAF_AHOY_SCRIPT (set by baseline scripts) > ABLATION_MODE (legacy) > default
if ($env:MAF_AHOY_SCRIPT) {
	$genericAgent = $env:MAF_AHOY_SCRIPT
	Write-Host "Using MAF_AHOY_SCRIPT: $genericAgent" -ForegroundColor Cyan
} else {
	# Fallback to ABLATION_MODE check for backward compatibility
	$ablationMode = $env:ABLATION_MODE
	if ($ablationMode) {
		Write-Host "ABLATION_MODE detected: $ablationMode" -ForegroundColor Yellow
		switch ($ablationMode) {
			"baseline0_full" {
				$genericAgent = "ablation/baseline0_full/ahoy.py"
			}
			"baseline1_no_comments" {
				$genericAgent = "ablation/baseline1_no_comments/ahoy.py"
			}
			"baseline2_no_filtering" {
				$genericAgent = "ablation/baseline2_no_filtering/ahoy.py"
			}
			default {
				$genericAgent = "agents/ahoy.py"
			}
		}
	} else {
		$genericAgent = "agents/ahoy.py"
	}
}
$full = Join-Path $scriptDir $genericAgent
if (Test-Path $full) {
	try {
		# CRITICAL: Always use repository root as working directory
		# Baseline agents (ablation/baseline*/ahoy.py) import from agents.ahoy
		# which requires running from the project root
		$scriptWorkingDir = $scriptDir
		$agentName = [System.IO.Path]::GetFileNameWithoutExtension($genericAgent)
		$agentLog = Join-Path $logDir ("$agentName.log")
		$tempName = "$agentName-$([guid]::NewGuid().ToString()).err"
		$agentErr = Join-Path $env:TEMP $tempName
		$proc = Start-Process -FilePath $pythonExe -ArgumentList @('-u', $full) -WorkingDirectory $scriptWorkingDir -RedirectStandardOutput $agentLog -RedirectStandardError $agentErr -NoNewWindow -PassThru
		if ($proc) {
			# Now set the claimed role file path based on the generic agent PID
			$claimedRoleFile = Join-Path $env:TEMP "maf_claimed_role_$($proc.Id).txt"
			$startedProcs += @{ Name = $agentName; Proc = $proc; Log = $agentLog; Err = $agentErr }
			$line = "Started $genericAgent (pid $($proc.Id)) at $(Get-Date -Format o)"
			Write-Host $line
			
			# Wait for generic agent to write claimed role file (with timeout)
			Write-Host "Waiting for LLM agent to determine claimed role (max 10 seconds)..."
			$maxWait = 10
			$waited = 0
			while ((-not (Test-Path $claimedRoleFile)) -and ($waited -lt $maxWait)) {
				Start-Sleep -Milliseconds 500
				$waited += 0.5
			}
			
			if (Test-Path $claimedRoleFile) {
				$claimedRolesStr = Get-Content -Path $claimedRoleFile -Raw
				Write-Host "LLM agent claimed roles: $claimedRolesStr"
				
				# Parse claimed roles (format: "Protocol:Role" or "Protocol:Role,Protocol:Role,...")
				# Multi-role support: ahoy can now claim multiple roles across different protocols
				$claimedRoles = @()
				if ($claimedRolesStr -match ',') {
					# Multiple roles (comma-separated)
					$claimedRoles = $claimedRolesStr.Split(',') | ForEach-Object { $_.Trim() }
				} else {
					# Single role
					$claimedRoles = @($claimedRolesStr.Trim())
				}
				Write-Host "Parsed claimed roles for skipping: [$($claimedRoles -join ', ')]"
				if ($claimedRoles.Count -gt 1) {
					Write-Host "  → Ahoy is running multiple roles: $($claimedRoles -join ' + ')"
				}
			} else {
				Write-Host "Warning: LLM agent did not write claimed role file within timeout"
				$claimedRoles = @()
			}
		}
	} catch {
		$msg = "Failed to start ${genericAgent}: ${_}"
		Write-Host $msg
	}
}

# Now start all other agents EXCEPT the ones claimed by ahoy (multi-role support)
Write-Host ""
Write-Host "Starting hardcoded background agents (excluding roles claimed by ahoy)..."
Write-Host "  Note: Ahoy can now claim multiple roles across different protocols"

# Filter out:
# 1. The generic agent (exact match)
# 2. agents/ahoy.py if using a custom generic agent (to avoid launching the standard ahoy when using baselines)
$agents = $allAgents | Where-Object { 
	$_ -ne $genericAgent -and
	-not (($_ -eq "agents/ahoy.py") -and ($genericAgent -ne "agents/ahoy.py"))
}

$startedAny = $false

foreach ($a in $agents) {
	# Check if this agent's role was claimed by ahoy (supports multi-role scenarios)
	if ($agentRoles.ContainsKey($a)) {
		$agentRole = $agentRoles[$a]
		
		# Check if this role is in the claimed roles list (supports multiple roles)
		if ($agentRole -in $claimedRoles) {
			Write-Host "  Skipping $a (role $agentRole claimed by ahoy)"
			continue
		}
	}
	
	$full = Join-Path $scriptDir $a
	if (Test-Path $full) {
		Write-Host "Starting $a..."
		try {
			$scriptWorkingDir = Split-Path -Parent $full
			$agentName = [System.IO.Path]::GetFileNameWithoutExtension($a)
			$agentLog = Join-Path $logDir ("$agentName.log")
			$tempName = "$agentName-$([guid]::NewGuid().ToString()).err"
			$agentErr = Join-Path $env:TEMP $tempName
			$pythonExe = "C:\\Users\\Omkar\\miniconda3\\envs\\maf-py\\python.exe"
			$proc = Start-Process -FilePath $pythonExe -ArgumentList @('-u', $full) -WorkingDirectory $scriptWorkingDir -RedirectStandardOutput $agentLog -RedirectStandardError $agentErr -NoNewWindow -PassThru
			if ($proc) {
				$startedProcs += @{ Name = $agentName; Proc = $proc; Log = $agentLog; Err = $agentErr }
				$startedAny = $true
				$line = "Started $a (pid $($proc.Id)) at $(Get-Date -Format o)"
				Write-Host $line
			}
		} catch {
			$msg = "Failed to start ${a}: ${_}"
			Write-Host $msg
		}
	} else {
		Write-Host "Skipping $a (not found)"
	}
}

if (-not $startedAny) {
	Write-Host "No agent scripts were found/started. Exiting."
	exit 1
}

Write-Host ""
Write-Host "=== Multi-Agent Configuration ===" 
Write-Host "Python executable: $pythonExe"
if ($claimedRoles.Count -gt 0) {
	Write-Host "Ahoy claimed roles: $($claimedRoles -join ', ')"
} else {
	Write-Host "Ahoy claimed roles: (none detected yet)"
}
Write-Host "All agents started. Consolidated log: $logFile"
Write-Host "===================================="
Write-Host "Press any key to stop agents and free ports..."

$readers = @()
foreach ($entry in $startedProcs) {
	$outPath = $entry.Log
	$errPath = $entry.Err
	if (-not (Test-Path $outPath)) { New-Item -Path $outPath -ItemType File | Out-Null }
	if (-not (Test-Path $errPath)) { New-Item -Path $errPath -ItemType File | Out-Null }
	
	$fsOut = [System.IO.File]::Open($outPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
	$srOut = New-Object System.IO.StreamReader($fsOut, [System.Text.Encoding]::UTF8)
	try { $fsOut.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null } catch { }
	$readers += @{ Name = $entry.Name; Stream = $srOut; FileStream = $fsOut; Type = 'out' }
	
	$fsErr = [System.IO.File]::Open($errPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
	$srErr = New-Object System.IO.StreamReader($fsErr, [System.Text.Encoding]::UTF8)
	try { $fsErr.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null } catch { }
	$readers += @{ Name = $entry.Name; Stream = $srErr; FileStream = $fsErr; Type = 'err' }
}

# Loop until a key is pressed
while (-not [Console]::KeyAvailable -and -not (Test-Path "$env:TEMP\maf_stop_signal.txt")) {
	foreach ($r in $readers) {
		$sr = $r.Stream
		while (-not $sr.EndOfStream) {
			$line = $sr.ReadLine()
			if ($line -ne $null) {
				Write-Host "$line"
			}
		}
	}
	Start-Sleep -Milliseconds 150
}

# Check if we stopped due to stop signal
if (Test-Path "$env:TEMP\maf_stop_signal.txt") {
	Write-Host "`nStop signal detected - shutting down all agents gracefully...`n"
} else {
	[Console]::ReadKey($true) | Out-Null
}

Write-Host "Stopping jobs and terminating matching python processes..."

# Stop and remove processes we started
foreach ($entry in $startedProcs) {
	$p = $entry.Proc
	try {
		Write-Host "Stopping pid $($p.Id)"
		Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue
	} catch {
		Write-Host "Failed to stop pid $($p.Id): $_"
	}
}

# Wait for processes to exit
foreach ($entry in $startedProcs) {
	$p = $entry.Proc
	try {
		if (-not $p.HasExited) { $p.WaitForExit(2000) }
		if ($p.HasExited) {
			$ec = $p.ExitCode
			$line = "Process $($entry.Name) (pid $($p.Id)) exited with code $ec"
			Write-Host $line
		} else {
			$line = "Process $($entry.Name) (pid $($p.Id)) did not exit within timeout"
			Write-Host $line
		}
	} catch {
		Write-Host "Failed to obtain exit code for pid $($p.Id): $_"
	}
}

# Close all readers
foreach ($r in $readers) {
	try { $r.Stream.Close() } catch { }
	try { $r.FileStream.Close() } catch { }
}

# Append err files into logs
foreach ($entry in $startedProcs) {
	try {
		if (Test-Path $entry.Err) {
			$errLength = (Get-Item $entry.Err).Length
			if ($errLength -gt 0) {
				Get-Content -Path $entry.Err -ErrorAction SilentlyContinue | Out-File -FilePath $entry.Log -Append -Encoding utf8
				Remove-Item -Path $entry.Err -ErrorAction SilentlyContinue
			} else {
				Remove-Item -Path $entry.Err -ErrorAction SilentlyContinue
			}
		}
	} catch {
		Write-Host "Warning: failed to merge or remove err file for $($entry.Name): $_"
	}
}

# Combine all per-agent logs into a single consolidated file
$combined = $logFile
"--- Combined agent log started: $(Get-Date -Format o) ---" | Out-File -FilePath $combined -Encoding utf8
foreach ($entry in $startedProcs) {
	try {
		"`n--- Agent: $($entry.Name) ---" | Out-File -FilePath $combined -Append -Encoding utf8
		if (Test-Path $entry.Log) {
			Get-Content -Path $entry.Log -ErrorAction SilentlyContinue | Out-File -FilePath $combined -Append -Encoding utf8
		}
	} catch {
		Write-Host "Warning: failed to append $($entry.Name) log to combined log: $_"
	}
}
"--- Combined agent log ended: $(Get-Date -Format o) ---" | Out-File -FilePath $combined -Append -Encoding utf8

# Find and terminate lingering python processes
try {
	$pyProcs = Get-CimInstance Win32_Process -Filter "Name = 'python.exe' OR Name = 'python3.exe'" -ErrorAction SilentlyContinue
	foreach ($a in $agents) {
		foreach ($p in $pyProcs) {
			if ($p.CommandLine -and $p.CommandLine -match [regex]::Escape($a)) {
				Write-Host "Terminating process $($p.ProcessId) (matches $a)"
				try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop } catch { Write-Host "Failed to stop process $($p.ProcessId): $_" }
			}
		}
	}
} catch {
	Write-Host "Warning: failed to enumerate/terminate python processes cleanly: $_"
}

Write-Host "Shutdown complete. Logs written to $logFile"

# Clean up stop signal file
try {
	if (Test-Path "$env:TEMP\maf_stop_signal.txt") {
		Remove-Item -Path "$env:TEMP\maf_stop_signal.txt" -Force -ErrorAction SilentlyContinue
	}
} catch {
	Write-Host "Warning: failed to clean up stop signal file: $_"
}


