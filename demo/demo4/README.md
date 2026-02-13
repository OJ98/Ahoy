# DEMO 4: Custom Events Integration

**Demo 4** demonstrates how external systems can inject custom events into running agents without breaking protocol-driven behavior. The example shows an external purchase request system injecting a "bat purchase" event with delivery address and budget constraints.

## Quick Start

```powershell
cd C:\PhD\Research\MultiAgents\Code\MAF
.\demo\demo4\run_demo4.ps1
```

Results saved to: `demo/demo4/results/demo4_YYYYMMDD_HHMMSS.*`

## What Happens

1. **Environment Setup**: Activates `maf-py` conda environment
2. **Agent Startup**: Launches agents for Purchase protocol (Buyer, Seller, Shipper)
3. **Event Injection**: External system injects a custom event:
   - Event: Request to buy a bat
   - Fields: `delivery_address`, `budget`
   - Agent's LLM considers this constraint when making purchase decisions
4. **Protocol Execution**: Agent executes the Purchase protocol while aware of the external context
5. **Logging**: Records all decisions and event processing
6. **Analysis**: Post-execution report showing event processing and metrics

## Architecture Overview

```
External Purchase System (event_simulator.py)
    ↓ Injects: "Buy bat" with delivery address & budget
Event Queue in ahoy.py
    ↓
LLM Decision Handler
    (Checks: Do we need to buy a bat? Budget? Delivery?)
    ↓
Agent Makes Purchase Decision
    (Considering protocol state + external request)
    ↓
Sends Protocol Messages (Purchase → Shipping)
```

## Implementation Details

### Event Injection (event_simulator.py)

The simulator injects a single event for purchasing a bat:

```python
post_event_to_agent(
    event_type="user_defined",
    message="Purchase request: Buy a bat",
    priority="high",
    metadata={
        "item": "bat",
        "delivery_address": "123 Main St, Springfield",
        "budget": 29.99
    }
)
```

### Integration Points

- **ahoy.py**: Event queue initialized, LLM decision handler checks for pending events
- **event_injector.py**: External systems post events via `post_event_to_agent()`
- **demo4_harness.py**: Orchestrates agents + event injection
- **event_analyzer.py**: Analyzes event processing and produces metrics

## Key Design Principles

1. **Non-Breaking**: Existing agents work unchanged
2. **Decoupled**: External systems are independent of protocol logic
3. **Simple**: Single event demonstrates the concept clearly
4. **Logged**: Full audit trail of event injection and processing

## Expected Output

The demo produces:
- `demo4_YYYYMMDD_HHMMSS.log`: Full execution trace (DEBUG level)
- `demo4_events_YYYYMMDD_HHMMSS.json`: Injected events log
- `demo4_analysis_YYYYMMDD_HHMMSS.json`: Metrics and analysis

### Example Analysis

```json
{
  "events_injected": 1,
  "event_type": "user_defined",
  "event_description": "Purchase request: Buy a bat",
  "event_metadata": {
    "item": "bat",
    "delivery_address": "123 Main St, Springfield",
    "budget": 29.99
  },
  "protocol_execution": "Purchase protocol completed with external context"
}
```

## Customizing the Event

Edit `event_simulator.py` to modify the bat purchase event:

```python
# Change the item, address, or budget
post_event_to_agent(
    event_type="user_defined",
    message="Purchase request: Buy a <your_item>",
    priority="high",
    metadata={
        "item": "<item_name>",
        "delivery_address": "<new_address>",
        "budget": <new_budget>
    }
)
```

## Files in This Demo

| File | Purpose |
|------|---------|
| `demo4_harness.py` | Main orchestrator - starts agents and simulator |
| `event_simulator.py` | Injects the bat purchase event |
| `event_analyzer.py` | Analyzes results and produces metrics report |
| `run_demo4.ps1` | PowerShell launcher |
| `results/` | Output directory for logs and analysis |

## Troubleshooting

**Event not injected**: Check agent is running
```powershell
Get-Content demo\demo4\results\demo4_*.log | Select-String "Purchase request"
```

**LLM not considering event**: Verify event context passed to LLM
```powershell
Get-Content demo\demo4\results\demo4_*.log | Select-String "Pending custom events"
```

## For Researchers

This demo illustrates:
- External systems augmenting formal protocol execution
- Agent decision-making with real-world constraints
- Non-intrusive integration without modifying protocol logic

See [main README](../../README.md) for general architecture overview.
