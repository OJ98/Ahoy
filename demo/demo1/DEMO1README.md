# DEMO 1: Sequential Multi-Protocol Execution

**Demo 1** runs CHiPs-Ahoy with two protocols in sequence (Purchase, then Logistics), with comprehensive logging and automated metrics aggregation.

## Quick Start

```powershell
cd C:\PhD\Research\MultiAgents\Code\MAF
.\demo\run_demo1.ps1
```

Results saved to: `demo/results/demo1_YYYYMMDD_HHMMSS.*`

## What Happens

1. **Environment Setup**: Activates `maf-py` conda environment
2. **Agent Startup**: Launches 7 agents (Purchase + Logistics roles)
3. **Protocol 1 (Purchase)**: Buyer, Seller, Shipper - e-commerce transaction
   - Detailed logging to `demo/results/demo1_TIMESTAMP.log`
   - Metrics collected from agent_notes.json
4. **Protocol 2 (Logistics)**: Merchant, Packer, Labeler, Wrapper - fulfillment
   - Detailed logging appended to same log file
   - Fresh agent state, new metrics collection
5. **Analysis**: Post-execution metrics aggregation and report
6. **Output**: Results saved to `demo/results/`

## Execution Flow

```
1. Setup logging (DEBUG to file, INFO to console)
2. Clear previous state (agent_notes, stop signals)
3. START ALL AGENTS for both protocols
4. Execute Protocol 1 (Purchase)
   ├─ Wait for completion or 60s timeout
   ├─ Collect metrics from agent_notes.json
   └─ Signal agents to stop
5. Clear state and restart agents
6. Execute Protocol 2 (Logistics)
   ├─ Wait for completion or 60s timeout
   ├─ Collect metrics from agent_notes.json
   └─ Signal agents to stop
7. Run post-analysis
8. Print summary report
9. Terminate all agents
```

## Files & Components

| File | Purpose |
|------|---------|
| `demo1_harness.py` | Main orchestration (start agents, execute protocols, collect metrics) |
| `demo1_analysis.py` | Post-execution analysis (aggregate metrics, generate reports) |
| `batch_analysis.py` | Batch analysis across multiple runs (for paper evaluation) |
| `run_demo1.ps1` | PowerShell launcher with environment setup |

## Output & Results

Results are saved in `demo/results/` with timestamp:

```
demo1_20260130_120000.log              # Detailed execution log (DEBUG level)
demo1_20260130_120000.json             # Metrics in JSON format
demo1_20260130_120000_analysis.json    # Analysis report with aggregates
```

### Metrics Collected

For each protocol:
- **Execution Time**: Total time from agent start to completion
- **LLM Calls**: Total Claude API calls across all agents
- **LLM Duration**: Total time spent in LLM inference
- **Agent Decision Counts**: Decisions made by each agent (framework ready)
- **Agent Message Counts**: Messages sent per agent (framework ready)
- **Protocol Success**: Whether protocol completed successfully

### Example Results JSON

```json
{
  "run_timestamp": "20260130_120000",
  "protocols_executed": ["Purchase", "Logistics"],
  "metrics": [
    {
      "protocol_name": "Purchase",
      "execution_time": 22.15,
      "llm_call_count": 18,
      "llm_duration_seconds": 8.34,
      "success": true
    },
    {
      "protocol_name": "Logistics",
      "execution_time": 23.08,
      "llm_call_count": 17,
      "llm_duration_seconds": 7.33,
      "success": true
    }
  ]
}
```

### Example Analysis Report

```json
{
  "demo_summary": {
    "run_timestamp": "20260130_120000",
    "total_protocols_executed": 2,
    "protocols_successful": 2,
    "success_rate": "100.0%",
    "total_execution_time_seconds": 45.23,
    "total_llm_calls": 35,
    "average_llm_calls_per_protocol": 17.5,
    "average_execution_time_per_protocol": 22.62
  },
  "protocol_metrics": [
    {
      "protocol": "Purchase",
      "success": true,
      "execution_time_seconds": 22.15,
      "llm_calls": 18,
      "llm_duration_seconds": 8.34
    }
  ]
}
```

## Logging

**Two-tier logging system:**

| Level | Destination | Detail |
|-------|-------------|--------|
| **DEBUG** | File only | Ultra-detailed operation traces |
| **INFO** | Console + File | Key events and milestones |

### Log File Example

```
2026-01-30 12:00:00 [DEBUG] Started agent process: buyer.py (PID: 1234)
2026-01-30 12:00:00 [INFO] Starting agents for Purchase protocol...
2026-01-30 12:00:00 [INFO]   ✓ buyer.py started (PID: 1234)
2026-01-30 12:00:02 [DEBUG] Monitoring with timeout: 60s
2026-01-30 12:00:15 [INFO] Protocol Purchase completed!
2026-01-30 12:00:15 [INFO] Execution Time: 22.15s
2026-01-30 12:00:15 [INFO] LLM Calls: 18
```

### Console Output Example

```
=======================================================================
DEMO 1: Sequential Multi-Protocol Execution
=======================================================================

[2026-01-30 12:00:00] [INFO] Starting agents for Purchase protocol...
[2026-01-30 12:00:00] [INFO]   ✓ buyer.py started (PID: 1234)
[2026-01-30 12:00:02] [INFO] Waiting for Purchase protocol to complete...
[2026-01-30 12:00:15] [INFO] Protocol Purchase completed!

[2026-01-30 12:00:17] [INFO] Starting agents for Logistics protocol...
[2026-01-30 12:00:30] [INFO] Protocol Logistics completed!

=======================================================================
DEMO 1 ANALYSIS REPORT
=======================================================================

Execution Summary:
  Run Timestamp: 20260130_120000
  Protocols Executed: 2
  Successful: 2/2
  Success Rate: 100.0%

Timing Metrics:
  Total Execution Time: 45.23s
  Avg per Protocol: 22.62s

LLM Metrics:
  Total LLM Calls: 35
  Avg Calls per Protocol: 17.5
  Total LLM Duration: 15.67s

=======================================================================
```

## Viewing Results

```powershell
# List all results
Get-ChildItem demo\results\

# View latest results JSON
$latest = Get-ChildItem demo\results\demo1_*.json -Exclude *_analysis | Sort-Object LastWriteTime -Desc | Select-Object -First 1
Get-Content $latest.FullName | ConvertFrom-Json | ConvertTo-Json -Depth 10

# View detailed log
$log = Get-ChildItem demo\results\*.log | Sort-Object LastWriteTime -Desc | Select-Object -First 1
Get-Content $log.FullName | Select-Object -Last 50  # Last 50 lines
```

## State Management

### Agent Notes

Agent state stored in: `logs/agent_notes/agent_notes.json`

Cleared before each protocol run. Agents write during execution:

```json
{
  "Buyer": {
    "decisions": 5,
    "messages_sent": 12
  },
  "Seller": {
    "decisions": 3,
    "messages_sent": 8
  }
}
```

### Stop Signal

Cross-platform protocol completion signaling:
- **File**: `%TEMP%/maf_stop_signal.txt` (Windows) or `/tmp/maf_stop_signal.txt` (Unix)
- **Usage**: Set after each protocol completes to gracefully shutdown agents
- **Cleared**: Before each protocol run

## Batch Analysis (Multiple Runs)

For paper evaluation or statistical analysis across multiple runs:

```powershell
# Run demo 5 times
1..5 | ForEach-Object { python demo\demo1_harness.py }

# Analyze all runs
python demo\batch_analysis.py demo\results
```

Output includes:
- Mean, stdev, min, max execution times
- Mean, stdev, min, max LLM calls
- Aggregate success rates
- Saved to `batch_analysis_TIMESTAMP.json`

## Customization

### Change Protocols

Edit `PROTOCOLS` list in `demo1_harness.py`:

```python
PROTOCOLS = [
    {
        "name": "Purchase",
        "roles": ["Buyer", "Seller", "Shipper"],
        "agents": ["buyer.py", "seller.py", "shipper.py"],
        "input_file": PROJECT_ROOT / "input_purchase.txt",
    },
    # Add more protocols...
]
```

### Adjust Timeout

```python
metrics = await execute_protocol(protocol_config, max_wait_time=120)  # seconds
```

### Change LLM Constraints

```python
initialize_llm_tracker(max_calls=30, max_duration_seconds=300)
```

### Add Custom Metrics

Modify `ProtocolMetrics` dataclass in `demo1_harness.py`:

```python
@dataclass
class ProtocolMetrics:
    # ... existing fields ...
    custom_field: float = 0.0
```

## Troubleshooting

**Agents won't start:**
```powershell
# Verify environment
conda activate maf-py
conda list | grep bspl
```

**Port conflicts:**
```powershell
# Kill existing Python processes
Get-Process python | Stop-Process -Force
```

**Protocol times out:**
1. Increase `max_wait_time` in harness (default: 60s)
2. Check agent logs: `logs/agent_notes/agent_notes.json`
3. Check detailed log: `demo/results/demo1_TIMESTAMP.log`

**Check logs:**
```powershell
# Latest detailed log (last 100 lines)
$log = Get-ChildItem demo\results\*.log | Sort-Object LastWriteTime -Desc | Select-Object -First 1
Get-Content $log.FullName | Select-Object -Last 100

# Validate results JSON
$json = Get-ChildItem demo\results\demo1_*.json -Exclude *_analysis | Sort-Object LastWriteTime -Desc | Select-Object -First 1
Get-Content $json.FullName | ConvertFrom-Json
```

**Missing input files:**
Verify these exist:
- `input_purchase.txt`
- `input_logistics.txt`

## Architecture

### LLM Integration

- Model: `claude-haiku-4-5-20251001`
- Tracked via `lib/llm_client.LLMCallTracker`
- Default limits: 20 calls, 180s duration
- Per-protocol reset for fair comparison

### Agent Coordination

1. Agents claim roles via temp files: `%TEMP%/maf_claimed_role_{PID}.txt`
2. Harness monitors stop signal: `%TEMP%/maf_stop_signal.txt`
3. Each protocol run is isolated (separate agent state)

### Metrics Collection

- LLM calls/duration from `lib/llm_client.LLMCallTracker`
- Agent metrics from `logs/agent_notes/agent_notes.json`
- Execution timing from process lifetime
- Results serialized to JSON for analysis

## Integration Points

The harness integrates with:

- **LLM Client** (`lib/llm_client.py`): Call tracking and duration
- **Agent Notes** (`lib/agent_notes.py`): Per-agent metrics
- **Configuration** (`configuration.py`): Protocol definitions
- **Protocol Discovery** (`lib/protocol_discovery.py`): Available protocols

## Next Steps

1. **Run the demo**: `.\demo\run_demo1.ps1`
2. **Check results**: `demo\results\demo1_TIMESTAMP.json`
3. **View analysis**: `demo\results\demo1_TIMESTAMP_analysis.json`
4. **View detailed log**: `demo\results\demo1_TIMESTAMP.log`
5. **Multiple runs**: Run 5-10 times for statistical analysis
6. **Batch analysis**: `python demo\batch_analysis.py demo\results`

## Files Ready for Integration

All components are production-ready for:
- ✅ Paper evaluation and statistics generation
- ✅ Thesis demonstration and results collection
- ✅ Automated testing and CI/CD pipelines
- ✅ Comparative analysis across configurations
