# DEMO 3: Concurrent Multi-Protocol Participation  

**Demo 3** demonstrates TRUE concurrent multiprotocol participation: a **single LLM-driven agent simultaneously plays roles in two protocols** (Purchase *and* Logistics), coordinating both protocol contexts in parallel.

## Architecture Innovation

Instead of multiple agents, **one agent** enters both protocol spaces:
- **Role 1**: Buyer in Purchase protocol  
- **Role 2**: Merchant in Logistics protocol

The agent handles both role contexts concurrently while supporting agents handle specialized tasks in each protocol.

## Quick Start

```powershell
cd C:\PhD\Research\MultiAgents\Code\MAF
.\demo\demo3\run_demo3.ps1
```

Results saved to: `demo/demo3/results/demo3_YYYYMMDD_HHMMSS.*`

## What Happens

1. **Configuration**: Configure ahoy.py for MULTIPLE roles: `Purchase:Buyer;Logistics:Merchant`
2. **Supporting Agents**: Start hardcoded agents needed for both protocols (Seller, Shipper, Wrapper, Labeler, Packer)
3. **Multiprotocol Agent**: ONE ahoy.py instance starts, simultaneously playing both roles
4. **Concurrent Coordination**: 
   - Agent makes decisions in Purchase context (buying items)
   - Agent makes decisions in Logistics context (fulfilling orders)
   - Both happen concurrently within a single agent process
5. **Metrics & Analysis**: Collect performance metrics across both protocol executions
6. **Output**: Results saved showing single-agent multiprotocol performance

## Execution Flow

```
1. Setup logging (DEBUG to file, INFO to console)
2. Clear previous state (temp files, stop signals)
3. START SUPPORTING AGENTS (both proto cols)
   ├─ Seller, Shipper for Purchase
   └─ Wrapper, Labeler, Packer for Logistics
4. START ONE AHOY.PY WITH MULTIPLE ROLES
   ├─ Role 1: Buyer (Purchase)
   └─ Role 2: Merchant (Logistics)
5. MONITOR CONCURRENT EXECUTION
   ├─ Agent handles both protocol contexts in parallel
   ├─ Collect real-time metrics from agent logs
   └─ Wait for both protocols to complete (or 120s timeout)
6. ANALYZE MULTIPROTOCOL PERFORMANCE
7. PRINT SUMMARY (single agent, dual protocol metrics)
8. Terminate all agents
```

## Files & Components

| File | Purpose |
|------|---------|
| `demo3_harness.py` | Main orchestration (concurrent agent startup, parallel protocol execution, metrics aggregation) |
| `demo3_analysis.py` | Post-execution analysis (aggregate metrics, generate reports for multiprotocol runs) |
| `run_demo3.ps1` | PowerShell launcher with environment setup |

## Output & Results

Results are saved in `demo/demo3/results/` with timestamp:

```
demo3_20260130_120000.log              # Detailed execution log (DEBUG level, all agents)
demo3_20260130_120000.json             # Metrics in JSON format
demo3_20260130_120000_analysis.json    # Analysis report with aggregates
```

### Metrics Collected

For multiprotocol concurrent execution:
- **Execution Time**: Total time from agent start to all protocols complete
- **LLM Calls**: Total Claude API calls across ALL agents
- **LLM Duration**: Total time spent in LLM inference
- **Agent Message Counts**: Messages sent per agent per protocol
- **Protocol-Specific Success**: Whether each protocol completed successfully
- **Concurrent Efficiency**: Metrics showing parallel execution benefits

### Example Results JSON

```json
{
  "run_timestamp": "20260130_120000",
  "execution_mode": "concurrent",
  "protocols_executed": ["Purchase", "Logistics"],
  "total_execution_time": 35.42,
  "metrics": [
    {
      "protocol_name": "Purchase",
      "role_name": "Buyer",
      "execution_time": 28.15,
      "llm_call_count": 9,
      "llm_duration_seconds": 4.12,
      "success": true
    },
    {
      "protocol_name": "Logistics",
      "role_name": "Merchant",
      "execution_time": 35.42,
      "llm_call_count": 11,
      "llm_duration_seconds": 5.23,
      "success": true
    }
  ],
  "concurrent_analysis": {
    "protocols_completed_in_parallel": true,
    "time_saved_vs_sequential": 17.08,
    "total_llm_calls": 20,
    "total_llm_duration": 9.35
  }
}
```

## Key Differences from Demo 1

| Aspect | Demo 1 (Sequential Multi-Protocol) | Demo 3 (Concurrent Multiprotocol) |
|--------|-----------------------------------|-----------------------------------|
| **Agent Count** | Multiple agents (Buyer, Seller, Shipper, Merchant, Wrapper, etc.) | **One agent** playing two roles |
| **Protocol Execution** | Sequential: Purchase → Logistics | **Concurrent**: Both simultaneously |
| **Port Binding** | Each agent binds unique port | No conflict: single agent, single port |
| **Coordination Model** | Multi-agent choreography | **Protocol-agnostic LLM agent** |
| **Total Time** | Sum of protocol times | Lower than sum (parallel benefit) |
| **Use Case** | Testing individual protocols | **True multiprotocol participation** |
| **Architectural Test** | Multi-agent support | **Protocol-agnostic agent support** |

## What This Demonstrates

- **Protocol Agnosticism**: One agent seamlessly handles multiple protocol contexts without modification
- **Concurrent Multiprotocol**: No sequential waiting; agent makes decisions in both protocols in parallel
- **Architecture Validation**: Proves CHiPs-Ahoy design supports genuine multiprotocol agents
- **Scalability Foundation**: Shows path to extending beyond 2 protocols
- **Novel Contribution**: Demonstrates LLM-driven agents can coordinate across protocol boundaries in real-time

