# Minimal start script for starting agents in the maf-py environment.
# - Tries to activate `maf-py` (conda), falls back to common venv locations.
# - Starts agent scripts as background jobs and appends all their console
#   output (stdout+stderr) to a single log file: ./logs/agents.log
# - Waits for a keypress; then stops jobs and terminates any matching python processes
#   whose command line contains the agent script name (to free ports).

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

# Prepare logging
# The final combined per-agent log will be written to $logFile at shutdown.
$logDir = Join-Path $scriptDir "logs"
if (-not (Test-Path $logDir)) { New-Item -ItemType Directory -Path $logDir | Out-Null }
$logFile = Join-Path $logDir "agents.log"

# List of agent scripts to start
$agents = @("buyer.py", "seller.py", "shipper.py")

$startedAny = $false
# Track started processes so we can terminate them on shutdown
$startedProcs = @()
# Deferred log lines to write after processes have stopped (to avoid file-lock collisions)
# (no deferred runtime master log entries needed)

foreach ($a in $agents) {
	$full = Join-Path $scriptDir $a
	if (Test-Path $full) {
		Write-Host "Starting $a..."
		# Start as a background job; the job will run python and append stdout+stderr to the shared log
		# Important: set the job's working directory to the script's directory so that relative paths inside the
		# Python scripts (e.g. ./purchase.bspl) resolve correctly.
		# Use cmd.exe redirection to append both stdout and stderr to the shared log file.
		# This avoids PowerShell job output buffering and file-locking issues when multiple writers append to the same file.
		try {
			$scriptWorkingDir = Split-Path -Parent $full
			# Per-agent log file (e.g. logs\buyer.log)
			$agentName = [System.IO.Path]::GetFileNameWithoutExtension($a)
			$agentLog = Join-Path $logDir ("$agentName.log")
			# Create a temporary err file outside the repository logs so we don't leave .err files in the logs directory.
			$tempName = "$agentName-$([guid]::NewGuid().ToString()).err"
			$agentErr = Join-Path $env:TEMP $tempName
			# Start agent and redirect stdout and stderr to separate files to avoid Start-Process file-handle conflicts.
			# Use the hard-coded Python executable from the maf-py conda environment to ensure correct interpreter.
			$pythonExe = "C:\\Users\\Omkar\\miniconda3\\envs\\maf-py\\python.exe"
			# Start the python process (unbuffered) and redirect output to per-agent log and errors to a separate .err file.
			$proc = Start-Process -FilePath $pythonExe -ArgumentList @('-u', $full) -WorkingDirectory $scriptWorkingDir -RedirectStandardOutput $agentLog -RedirectStandardError $agentErr -NoNewWindow -PassThru
			if ($proc) {
				$startedProcs += @{ Name = $agentName; Proc = $proc; Log = $agentLog; Err = $agentErr }
				$startedAny = $true
				$line = "Started $a (pid $($proc.Id)) at $(Get-Date -Format o)"
				Write-Host $line
				# Not writing per-run master entries; combined log will be written at shutdown.
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

Write-Host "All requested agents started. Consolidated log: $logFile"
Write-Host "Press any key to stop agents and free ports..."

# Start combined viewer: tail per-agent log files and print prefixed lines to the console.
# We'll run a loop in the main thread that monitors each agent log file and prints any new lines with a prefix.
Write-Host "Starting combined live viewer for agent logs... (press any key to stop)"

# Open file streams for each agent log + err with shared read/write so writers can still append.
$readers = @()
foreach ($entry in $startedProcs) {
	$outPath = $entry.Log
	$errPath = $entry.Err
	if (-not (Test-Path $outPath)) { New-Item -Path $outPath -ItemType File | Out-Null }
	# Ensure the temp err file exists so the StreamReader can open it
	if (-not (Test-Path $errPath)) { New-Item -Path $errPath -ItemType File | Out-Null }
	# Open output stream
	$fsOut = [System.IO.File]::Open($outPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
	$srOut = New-Object System.IO.StreamReader($fsOut, [System.Text.Encoding]::UTF8)
	try { $fsOut.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null } catch { }
	$readers += @{ Name = $entry.Name; Stream = $srOut; FileStream = $fsOut; Type = 'out' }
	# Open error stream
	$fsErr = [System.IO.File]::Open($errPath, [System.IO.FileMode]::Open, [System.IO.FileAccess]::Read, [System.IO.FileShare]::ReadWrite)
	$srErr = New-Object System.IO.StreamReader($fsErr, [System.Text.Encoding]::UTF8)
	try { $fsErr.Seek(0, [System.IO.SeekOrigin]::End) | Out-Null } catch { }
	$readers += @{ Name = $entry.Name; Stream = $srErr; FileStream = $fsErr; Type = 'err' }
}

# Loop until a key is pressed; poll readers for new lines and print them with agent prefix.
while (-not [Console]::KeyAvailable) {
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

# Consume the pressed key so it doesn't appear in the console
[Console]::ReadKey($true) | Out-Null

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

# Wait briefly for processes to exit and log their exit codes for debugging
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

# Append any .err files into the main per-agent .log for a single consolidated file per agent,
# but avoid leaving .err files in the logs directory when they are empty.
foreach ($entry in $startedProcs) {
	try {
		if (Test-Path $entry.Err) {
			$errLength = (Get-Item $entry.Err).Length
			if ($errLength -gt 0) {
				# Append the error contents into the agent log and then delete the temp err file
				Get-Content -Path $entry.Err -ErrorAction SilentlyContinue | Out-File -FilePath $entry.Log -Append -Encoding utf8
				Remove-Item -Path $entry.Err -ErrorAction SilentlyContinue
			} else {
				# No errors: remove the empty temp file
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
		"\n--- Agent: $($entry.Name) ---" | Out-File -FilePath $combined -Append -Encoding utf8
		if (Test-Path $entry.Log) {
			Get-Content -Path $entry.Log -ErrorAction SilentlyContinue | Out-File -FilePath $combined -Append -Encoding utf8
		}
	} catch {
		Write-Host "Warning: failed to append $($entry.Name) log to combined log: $_"
	}
}
"--- Combined agent log ended: $(Get-Date -Format o) ---" | Out-File -FilePath $combined -Append -Encoding utf8

# Find any lingering python processes whose command line contains the script name and terminate them to free ports.
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

