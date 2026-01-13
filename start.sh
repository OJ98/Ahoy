#!/bin/bash

# Minimal start script for starting agents in the maf-py environment (macOS/Linux).
# - Activates `maf-py` conda environment
# - Starts agent scripts as background processes and logs output to ./logs/
# - Waits for interrupt (Ctrl+C); then stops jobs and cleans up

set -e

# Get the directory where this script lives
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Prepare logging
LOG_DIR="$SCRIPT_DIR/logs"
mkdir -p "$LOG_DIR"
MASTER_LOG="$LOG_DIR/agents.log"

# Initialize master log
echo "--- Combined agent log started: $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" > "$MASTER_LOG"

# Array to store background process IDs and their log files
declare -a PIDS
declare -a PID_NAMES
declare -a PID_LOGS

# Activate conda environment
echo "Activating environment 'maf-py'..."
if ! command -v conda &> /dev/null; then
	echo "conda not found in PATH. Make sure conda is installed and initialized."
	exit 1
fi

# Initialize conda in this shell session
eval "$(conda shell.bash hook)"
conda activate maf-py || { echo "Failed to activate maf-py environment"; exit 1; }

echo "Environment activated. Starting agents..."
echo ""

# List of agent scripts to start
# Note: generic_llm_agent.py is the main LLM-driven agent that reads from input.txt
#       Other agents are hardcoded background agents for various protocols:
#       - Purchase: buyer.py, seller.py, shipper.py
#       - Logistics: merchant.py, packer.py, labeler.py, wrapper.py
ALL_AGENTS=("agents/generic_llm_agent.py" "agents/buyer.py" "agents/seller.py" "agents/shipper.py" "agents/merchant.py" "agents/packer.py" "agents/labeler.py" "agents/wrapper.py")

# Mapping of agent files to their protocol and role
declare -A AGENT_ROLES=(
	["agents/buyer.py"]="Purchase:Buyer"
	["agents/seller.py"]="Purchase:Seller"
	["agents/shipper.py"]="Purchase:Shipper"
	["agents/merchant.py"]="Logistics:Merchant"
	["agents/packer.py"]="Logistics:Packer"
	["agents/labeler.py"]="Logistics:Labeler"
	["agents/wrapper.py"]="Logistics:Wrapper"
)

# Claimed role file will be set dynamically based on generic agent PID
# Placeholder - will be set after generic agent starts
$CLAIMED_ROLE_FILE=""

# Start generic_llm_agent first to determine which role it will claim
echo "Starting generic_llm_agent first to determine claimed role..."
GENERIC_AGENT="agents/generic_llm_agent.py"
full_path="$SCRIPT_DIR/$GENERIC_AGENT"
if [ -f "$full_path" ]; then
	agent_name="$(basename "${GENERIC_AGENT%.py}")"
	agent_log="$LOG_DIR/${agent_name}.log"
	
	echo "Starting $GENERIC_AGENT..."
	python -u "$full_path" > "$agent_log" 2>&1 &
	pid=$!
	
	# Set the claimed role file path based on generic agent PID
	CLAIMED_ROLE_FILE="$TMPDIR/maf_claimed_role_${pid}.txt"
	
	PIDS+=($pid)
	PID_NAMES+=("$agent_name")
	PID_LOGS+=("$agent_log")
	
	echo "  → Started with PID $pid (logging to $agent_log)"
	
	# Wait for generic agent to write claimed role file (with timeout)
	echo "Waiting for LLM agent to determine claimed role (max 10 seconds)..."
	max_wait=20  # 20 * 0.5 = 10 seconds
	waited=0
	while [ ! -f "$CLAIMED_ROLE_FILE" ] && [ $waited -lt $max_wait ]; do
		sleep 0.5
		waited=$((waited + 1))
	done
	
	if [ -f "$CLAIMED_ROLE_FILE" ]; then
		claimed_role=$(cat "$CLAIMED_ROLE_FILE" | tr -d '\n' | tr -d ' ')
		echo "✓ LLM agent claimed role: $claimed_role"
	else
		echo "⚠ Warning: LLM agent did not write claimed role file within timeout"
	fi
fi

echo ""
echo "Starting hardcoded background agents (excluding claimed role)..."
echo ""

# Now start all other agents EXCEPT the one claimed by LLM
for agent in "${ALL_AGENTS[@]}"; do
	if [ "$agent" = "$GENERIC_AGENT" ]; then
		continue  # Already started generic agent
	fi
	
	# Check if this agent's role was claimed by the LLM
	if [ -v AGENT_ROLES["$agent"] ]; then
		agent_role="${AGENT_ROLES[$agent]}"
		if [ -f "$CLAIMED_ROLE_FILE" ]; then
			claimed_role=$(cat "$CLAIMED_ROLE_FILE" | tr -d '\n' | tr -d ' ')
			agent_role_trimmed=$(echo "$agent_role" | tr -d '\n' | tr -d ' ')
			if [ "$claimed_role" = "$agent_role_trimmed" ]; then
				echo "Skipping $agent (role claimed by LLM agent: $agent_role)"
				continue
			fi
		fi
	fi
	
	full_path="$SCRIPT_DIR/$agent"
	if [ -f "$full_path" ]; then
		agent_name="$(basename "${agent%.py}")"
		agent_log="$LOG_DIR/${agent_name}.log"
		
		# Start the Python script as a background job
		echo "Starting $agent..."
		python -u "$full_path" > "$agent_log" 2>&1 &
		pid=$!
		
		PIDS+=($pid)
		PID_NAMES+=("$agent_name")
		PID_LOGS+=("$agent_log")
		
		echo "  → Started with PID $pid (logging to $agent_log)"
	else
		echo "Skipping $agent (not found)"
	fi
done

echo ""
if [ ${#PIDS[@]} -eq 0 ]; then
	echo "No agent scripts were found/started. Exiting."
	exit 1
fi

echo "All requested agents started."
echo "Combined log: $MASTER_LOG"
echo ""
echo "Live output:"
echo "---"

# Function to cleanup on exit
cleanup() {
	echo ""
	echo "---"
	echo ""
	echo "Stopping all agents..."
	
	for i in "${!PIDS[@]}"; do
		pid=${PIDS[$i]}
		name=${PID_NAMES[$i]}
		
		if kill -0 "$pid" 2>/dev/null; then
			echo "Terminating $name (PID $pid)..."
			kill -TERM "$pid" 2>/dev/null || true
			
			# Wait up to 2 seconds for graceful shutdown
			for j in {1..20}; do
				if ! kill -0 "$pid" 2>/dev/null; then
					break
				fi
				sleep 0.1
			done
			
			# Force kill if still running
			if kill -0 "$pid" 2>/dev/null; then
				echo "  → Force killing $name (PID $pid)"
				kill -9 "$pid" 2>/dev/null || true
			fi
		fi
	done
	
	# Combine all logs into master log
	for i in "${!PIDS[@]}"; do
		name=${PID_NAMES[$i]}
		log=${PID_LOGS[$i]}
		
		echo "" >> "$MASTER_LOG"
		echo "--- Agent: $name ---" >> "$MASTER_LOG"
		if [ -f "$log" ]; then
			cat "$log" >> "$MASTER_LOG"
		fi
	done
	
	echo "--- Combined agent log ended: $(date -u +%Y-%m-%dT%H:%M:%SZ) ---" >> "$MASTER_LOG"
	
	echo "Shutdown complete. Master log written to $MASTER_LOG"
}

# Register cleanup function to run on exit
trap cleanup EXIT

# Monitor and display live output from agent logs
while true; do
	for i in "${!PIDS[@]}"; do
		pid=${PIDS[$i]}
		name=${PID_NAMES[$i]}
		log=${PID_LOGS[$i]}
		
		# Check if process is still running
		if ! kill -0 "$pid" 2>/dev/null; then
			# Process has exited, show its final output if not yet shown
			if [ -f "$log" ]; then
				# Get new lines that haven't been shown yet
				tail -f "$log" 2>/dev/null &
				wait $!
			fi
		fi
		# Check for stop signal
		if [ -f "$TMPDIR/maf_stop_signal.txt" ]; then
			break 2  # Break out of both loops
		fi
	done
	
	sleep 0.5
done
