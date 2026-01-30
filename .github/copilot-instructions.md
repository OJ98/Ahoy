# CHiPs-Ahoy: AI Coding Agent Guide

## Project Overview

**CHiPs-Ahoy** is a multi-agent framework demonstrating LLM-driven agents coordinating through formally-specified BSPL (Blindingly Simple Protocol Language) protocols. Two protocols are supported:
1. **Purchase Protocol**: E-commerce (Buyer, Seller, Shipper)
2. **Logistics Protocol**: Supply chain (Merchant, Wrapper, Labeler, Packer)

## Architecture Essentials

### Key Design: Protocol-Agnostic LLM Agent

The system uses a **hybrid approach**: a single generic LLM agent dynamically adapts to any protocol, while hardcoded agents handle specific roles.

```
User Input → CHIPS (Interface) → LLM selects Protocol + Role → Generic Adapter → Protocol Interaction
```

**Critical Pattern**: LLM doesn't need role-specific implementations. The `Adapter` class (from BSPL library) bridges any protocol + role combination. See [agents/buyer.py](agents/buyer.py#L15) for example.

### Protocol Definition → Agent Reactions

1. **BSPL Specification** ([protocols/purchase.bspl](protocols/purchase.bspl)): Defines roles, messages, constraints
2. **Configuration Loading** ([configuration.py](configuration.py)): `bspl.load_file()` parses `.bspl` files and exports message types
3. **Agent Adapter** (e.g., [agents/wrapper.py](agents/wrapper.py)): Uses `@adapter.reaction(MessageType)` decorator for message handlers

**Do Not**: Manually create agent classes per protocol. Use dynamic adapter instantiation instead.

### Temp File Coordination System

Agents coordinate startup/shutdown via **PID-based temp files**:

- **Claimed Role**: `%TEMP%/maf_claimed_role_{PID}.txt` (stores `"Purchase:Buyer"` or `"Logistics:Wrapper"`)
- **Stop Signal**: `%TEMP%/maf_stop_signal.txt` (created when transaction completes)

**Why**: Prevents port conflicts (each agent role binds a unique port). See [start.ps1](start.ps1) for orchestration logic.

**Action**: Always use `shutdown_watcher(adapter, stop_path=str(STOP_SIGNAL_PATH))` to gracefully handle termination signals. Example: [agents/wrapper.py](agents/wrapper.py#L51).

## Critical Developer Workflows

### Running the System

1. **Interactive Setup**: `python chips.py`
   - Converses with user to infer protocol + role
   - Generates `input.txt` with scenario
   - Validates choices against available protocols

2. **Start All Agents**: `./start.ps1` (Windows) or `./start.sh` (Unix)
   - Activates `maf-py` conda environment
   - Monitors temp files to skip duplicate role launches
   - Appends all output to `logs/agents.log`

3. **Direct Agent Launch**: `python agents/buyer.py` (for testing single agent)

### Debugging Workflows

- **Protocol State Inspection**: Use [lib/state_manager.py](lib/state_manager.py) to extract serialized BSPL adapter state
- **Agent Logs**: Check `logs/{agent_name}.log` for detailed execution traces
- **Agent Notes**: Lightweight key-value store at `logs/agent_notes/agent_notes.json` (shared across agents, resets each run)
- **LLM Call Tracking**: [lib/llm_client.py](lib/llm_client.py#L16) enforces max_calls (20) and max_duration (180s) thresholds

## Code Patterns

### Adapter Reactions (Message Handlers)

```python
from Logistics import RequestWrapping, Wrapped
from bspl.adapter import Adapter

adapter = Adapter(Wrapper, systems, agents)

@adapter.reaction(RequestWrapping)
async def wrap(msg):
    """Process wrap requests. msg is typed message object."""
    wrapping = "bubblewrap" if msg["item"] in ["plate", "glass"] else "paper"
    await adapter.send(Wrapped(wrapping=wrapping, **msg.payload))
    return msg
```

**Key Points**:
- `@adapter.reaction(MessageType)`: Triggered when message is available (non-blocking)
- `@adapter.enabled(MessageType)`: Triggered when message CAN be sent (preconditions met)
- Message access: Use dict-like syntax `msg["field"]` or `.payload`
- Always `return msg` or `await adapter.send(response)` to maintain protocol state

### LLM Integration

```python
from lib.llm_client import AnthropicLLMClient

llm = AnthropicLLMClient()
response = llm.complete(
    messages=[{"role": "user", "content": "..."}],
    model=MODEL_ID
)
```

**Constraints**:
- Model: `claude-haiku-4-5-20251001` (default)
- Max calls: 20 per session
- Max duration: 180 seconds
- Tool calling supported for agent decision-making

### Configuration and Protocol Access

```python
from configuration import systems

# Access protocol metadata
purchase = systems["Purchase"]["protocol"]
buyer_role = purchase.roles["Buyer"]
```

Do NOT hardcode role/protocol names. Use configuration module.

## Critical Integration Points

| Component | File | Purpose |
|-----------|------|---------|
| **Protocol Loading** | [configuration.py](configuration.py) | Loads all `.bspl` files, creates message type exports |
| **Protocol Discovery** | [lib/protocol_discovery.py](lib/protocol_discovery.py) | Extracts protocol structure for LLM decision-making |
| **State Serialization** | [lib/state_manager.py](lib/state_manager.py) | Converts BSPL adapter state to JSON for LLM context |
| **LLM Communication** | [lib/llm_client.py](lib/llm_client.py) | Anthropic API client with call tracking + tool support |
| **Agent Notes** | [lib/agent_notes.py](lib/agent_notes.py) | Lightweight state persistence (JSON, resets each run) |

## Project-Specific Conventions

1. **Async/Await**: All agent code uses Python `asyncio`. Message sends are awaited: `await adapter.send(msg)`
2. **Logging**: Use [lib/ui_manager.py](lib/ui_manager.py#L20) patterns:
   - `setup_logging(filename)` returns `(debug_logger, console_logger)`
   - Debug logger goes to file; console logger to stdout
3. **Message Payloads**: Extract as dicts: `msg.payload`, `msg.key`, `msg.meta`
4. **Validation**: Always call `validate_protocol_and_role(protocol_name, role_name)` before instantiating adapter
5. **Stop Signal Path**: Use `Path(tempfile.gettempdir()) / "maf_stop_signal.txt"` (platform-agnostic)

## Common Pitfalls

- ❌ Launching multiple agents with same role simultaneously (causes port conflict)
- ❌ Forgetting to use `@adapter.reaction()` decorator (message never processed)
- ❌ Not awaiting `adapter.send()` (breaks async flow)
- ❌ Hardcoding protocol names instead of reading from `configuration.systems`
- ❌ Not using stop signal coordination (agents don't terminate cleanly)

## Adding New Protocols

1. Write BSPL specification in `protocols/{name}.bspl`
2. Add description line to [protocols/protocol_descriptions.txt](protocols/protocol_descriptions.txt)
3. Update [configuration.py](configuration.py) to load new protocol
4. Create agent implementations in `agents/{role}.py` (or reuse generic adapter)
5. Test via `chips.py` interactive interface

No changes needed to orchestration or LLM selection logic—it discovers protocols automatically.
