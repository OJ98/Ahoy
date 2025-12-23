# CHiPs-Ahoy: Creating Human-in-the-loop Interaction Protocols

This repository contains the code for **CHiPs-Ahoy**, a multi-agent framework that demonstrates how LLM-driven agents can collaborate through formally-specified communication protocols to execute complex, real-world business transactions.

## Overview

CHiPs-Ahoy (Creating Human-in-the-loop Interaction Protocols, Ahoy!) is a research project exploring the intersection of:
- **Formal Protocol Specification** (BSPL)
- **Large Language Models** (Claude AI)
- **Multi-agent Systems** (Distributed decision-making)
- **Human-in-the-loop Interaction** (User involvement in protocol execution)

The system demonstrates a fully-functional **Purchase Protocol** involving three independent agents (Buyer, Seller, Shipper) that negotiate and execute transactions through structured, formally-verified message exchanges while maintaining decision autonomy and budget constraints.

### Key Technologies

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Protocol Framework** | BSPL (Blindingly Simple Protocol Language) | Formal specification and enforcement of multi-agent communication rules |
| **AI/LLM** | Claude 3.5 Sonnet (Anthropic) | Intelligent agent decision-making with context awareness |
| **Concurrency** | Python asyncio | Parallel agent execution and non-blocking I/O |
| **Communication** | TCP/IP Sockets | Inter-agent message routing and synchronization |
| **State Management** | JSON Serialization | Protocol state tracking and agent context preservation |
| **Logging** | Timestamped Debug Logs | Comprehensive execution traces for analysis and debugging |

## Protocol: Purchase Transaction

The **Purchase Protocol** demonstrates a realistic e-commerce transaction involving three independent agents negotiating terms, executing payment, and coordinating delivery.

### Agents and Roles

**1. Buyer Agent** (`agents/buyer.py`)
- **Mission:** Identify and acquire a pen within specified constraints ($20 budget, delivery to Raleigh, NC 27606)
- **Decision Logic:** Uses Claude AI to evaluate quotes against constraints and make purchasing decisions
- **Behavior:** Initiates RFQs, compares multiple quotes, negotiates terms, verifies shipping capability
- **Constraints:** Must stay within budget, confirm delivery location, request shipping estimates before committing

**2. Seller Agent** (`agents/seller.py`)
- **Role:** Respond to quote requests and fulfill accepted orders
- **Decision Logic:** Provides dynamic pricing based on inventory and market conditions
- **Behavior:** Quotes prices, confirms orders, coordinates with Shipper for delivery
- **State Tracking:** Maintains order history and fulfillment status

**3. Shipper Agent** (`agents/shipper.py`)
- **Role:** Manage logistics and delivery operations
- **Decision Logic:** Handles shipping assignments and delivery confirmations
- **Behavior:** Receives shipping instructions from Seller, confirms delivery to buyer
- **Constraints:** Must verify delivery address and update status

### Message Flow and Protocol States

The purchase workflow follows this formal message sequence:

```
Phase 1: Quote Discovery
├─ Buyer → Seller:  rfq(ID, item)
│                   [Request for Quote]
│
└─ Seller → Buyer:  quote(ID, item, price)
                    [Price Quote Response]

Phase 2: Purchase Decision
├─ Buyer → Seller:  accept(ID, item, price, address, resp)
│                   [Accept offer and specify delivery address]
│
├─ Buyer → Seller:  reject(ID, item, price, outcome, resp)
│                   [Reject offer with reasoning]
│
└─ (Alternative: buyer waits for better quotes)

Phase 3: Fulfillment & Delivery
├─ Seller → Shipper: ship(ID, item, address)
│                    [Shipping instruction]
│
├─ Shipper → Buyer:  deliver(ID, item, address, outcome)
│                    [Delivery confirmation]
│
└─ Buyer → Seller:   completed(ID, item, price, satisfaction)
                     [Transaction completion & feedback]
```

### Protocol State Parameters

| Parameter | Type | Direction | Binding | Description |
|-----------|------|-----------|---------|-------------|
| **ID** | String | out | key | Unique transaction identifier (RFQ ID or Purchase ID) |
| **item** | String | out | derived | Product description (e.g., "pen") |
| **price** | Float | in | from quote | Negotiated purchase price in USD |
| **address** | String | out | - | Delivery address (Buyer specifies) |
| **outcome** | String | out | - | Transaction result reason (e.g., "Price acceptable", "Shipped successfully") |
| **resp** | String | out | - | Response message for acknowledgments |
| **satisfaction** | String | out | - | Buyer's satisfaction rating of completed transaction |
| **shipped** | Bool | in | from ship | Confirmation that item was shipped |

## System Architecture

### Multi-Agent Topology

The system uses a decentralized architecture with three independent agent processes communicating via TCP/IP sockets:

```
┌──────────────────────────────────────────────────────────┐
│                    Purchase Protocol                      │
│  Defined in BSPL (protocols/purchase.bspl)               │
└──────────────────────────────────────────────────────────┘
         ↓              ↓              ↓
    ┌─────────┐   ┌─────────┐   ┌──────────┐
    │  Buyer  │   │ Seller  │   │ Shipper  │
    │ Agent   │   │ Agent   │   │ Agent    │
    │ :8000   │   │ :8001   │   │ :8002    │
    └────┬────┘   └────┬────┘   └────┬─────┘
         │             │             │
         └─────────────┼─────────────┘
                       │
                 (TCP Message Queue)
```

**Network Configuration:**
- **Buyer Agent:** `127.0.0.1:8000`
- **Seller Agent:** `127.0.0.1:8001`
- **Shipper Agent:** `127.0.0.1:8002`

### Core Module Stack

```
┌─────────────────────────────────────────────────┐
│      Agent Decision Layer (agents/buyer.py)      │
│  • LLM-driven choice of enabled messages        │
│  • Constraint enforcement (budget, delivery)    │
│  • Decision reasoning and audit logging         │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│       LLM Integration (lib/llm_client.py)        │
│  • AnthropicLLMClient: Production Claude API    │
│  • MockLLMClient: Testing/development mode      │
│  • Call tracking, timeout management, retry     │
│  • Response parsing and validation              │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│   Protocol State Management & BSPL Adapter      │
│  • configuration.py: Protocol configuration     │
│  • lib/state_manager.py: State serialization    │
│  • Message validation & routing enforcement     │
│  • Binding resolution (parameter inheritance)   │
└─────────────────────────────────────────────────┘
                       ↓
┌─────────────────────────────────────────────────┐
│    UI and Logging (lib/ui_manager.py, utils.py) │
│  • Debug file output (JSON-compatible format)   │
│  • Console status updates with metrics          │
│  • Error reporting and transaction summaries    │
└─────────────────────────────────────────────────┘
```

### Component Descriptions

**1. Agent Executables** (`agents/buyer.py`, `agents/seller.py`, `agents/shipper.py`)
- Each agent implements a BSPL role with independent decision logic
- **Buyer:** Claude AI-powered with constraint checking and reasoning
- **Seller/Shipper:** Rule-based with deterministic behavior (extensible to LLM)
- All agents include lifecycle management: initialization, message loop, shutdown

**2. BSPL Adapter** (`configuration.py`)
- Loads the formal protocol specification from `protocols/purchase.bspl`
- Validates protocol rules and message schemas
- Manages state bindings and parameter inheritance
- Enforces enabled message constraints per BSPL semantics

**3. LLM Integration** (`lib/llm_client.py`)
- **AnthropicLLMClient:** Direct integration with Claude API
  - Configurable model selection (claude-3-5-sonnet-20241022)
  - Automatic timeout handling (30-second default)
  - Streaming response processing
  - Token limit awareness
- **MockLLMClient:** Deterministic testing mode
  - Returns fixed responses without API calls
  - Useful for development and testing
  - Maintains identical interface to production client
- **LLMCallTracker:** Monitors usage metrics
  - Counts total calls across session
  - Tracks elapsed time since initialization
  - Enforces call and time thresholds (default: 20 calls/3 minutes)
  - Graceful termination when thresholds exceeded

**4. State Management** (`lib/state_manager.py`)
- Extracts protocol state into JSON-serializable format
- Constructs social state: roles, bindings, message history
- Provides rich context for LLM decision-making
- Tracks message parameters for constraint checking

**5. UI/Logging** (`lib/ui_manager.py`)
- **Debug Logging:**
  - Timestamped file output in `logs/` directory
  - Complete LLM prompts and responses
  - Protocol state snapshots at each decision point
  - Enables full auditability and reproducibility
- **Status Updates:**
  - Minimal console output: message count + elapsed time
  - Format: `Status: N messages, Xs elapsed`
  - Non-intrusive feedback during execution

**6. Utilities** (`lib/utils.py`)
- Protocol requirements gathering from user input
- Message history construction for agent context
- User prompt generation with protocol documentation
- Graceful shutdown signal handling

## Advanced Features

### LLM Call Tracking and Budget Management

The system automatically monitors LLM resource consumption with dual thresholds:

**Thresholds:**
- **Call Limit:** 20 consecutive API calls maximum
- **Time Limit:** 3 minutes (180 seconds) from initialization

**Mechanism:**
1. `LLMCallTracker` initialized at agent startup
2. Each LLM call increments counter and checks elapsed time
3. When either threshold is exceeded, the system gracefully terminates
4. User receives clear explanation of which limit was exceeded

**Benefits:**
- Prevents runaway costs from LLM API overages
- Ensures predictable execution timeframes
- Enables testing with cost control

### Constraint-Based Agent Decision Making

The Buyer agent demonstrates intelligent constraint satisfaction:

**Constraints:**
```
- Budget: $20 USD maximum (inclusive of all fees)
- Delivery: Must be to Raleigh, NC 27606
- Product: Functional pen with reasonable quality
- Transparency: All cost components documented before purchase
```

**Decision Logic:**
1. Receives multiple quote options from different sellers
2. Filters options against constraints (price ≤ $20)
3. Evaluates shipping costs and delivery timeframes
4. Selects option that maximizes value while respecting constraints
5. Documents decision reasoning in audit log

**Audit Trail:**
```json
{
  "decision": "accept",
  "option": "RFQ_A4BC9F8D_2133",
  "reason": "Selected lower-priced quote ($4 vs $5), maximizes remaining budget for shipping",
  "constraints_satisfied": true,
  "remaining_budget": 16.0
}
```

### Protocol Binding and Parameter Resolution

BSPL enforces a formal parameter binding model:

**Parameter Categories:**
- **out:** Sender generates the value
- **in:** Receiver must already know the value (from prior message)
- **key:** Identifies the transaction instance

**Example Resolution:**
```
Seller quotes: quote(ID='RFQ_123', item='pen', price=5)
              ↓
Buyer receives binding: ID='RFQ_123', item='pen', price=5
              ↓
Buyer can now send: accept(ID='RFQ_123', item='pen', price=5, address='...', resp='...')
                           └─────────────────────────────────────────┬──────────────┘
                                              Buyer provides these values
```

This ensures type-safe message sequencing and prevents protocol violations.

## Requirements and Dependencies

### System Requirements
- **Python:** 3.8 or higher
- **OS:** Windows, macOS, or Linux
- **Network:** Localhost network access (127.0.0.1)

### Python Dependencies

Install with:
```bash
pip install -r requirements.txt
```

**Core Dependencies:**
- `anthropic`: Claude API client for LLM integration
- `bspl` (research package): Protocol specification framework
- `python-dotenv`: Environment variable configuration

**Development Dependencies:**
- `pytest`: Testing framework
- `black`: Code formatting
- `mypy`: Type checking

### API Configuration

Set your Anthropic API key as an environment variable:

```bash
# Linux/macOS
export ANTHROPIC_API_KEY="your-key-here"

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "your-key-here"
```

Or create a `.env` file in the project root:
```
ANTHROPIC_API_KEY=your-key-here
```

## Experimental Design and Research Context

### Research Questions

CHiPs-Ahoy was designed to answer:

1. **Can formally-specified protocols enable structured multi-agent collaboration?**
   - BSPL provides formal semantics for message sequencing
   - Agents must respect protocol constraints

2. **Can LLMs make intelligent decisions within formal protocol constraints?**
   - Claude makes decisions within BSPL-enforced message constraints
   - Reasoning capability enables complex constraint satisfaction

3. **How do we ensure transparency and auditability in multi-agent systems?**
   - Every decision logged with full reasoning
   - Protocol state captured at each step
   - Enables post-hoc analysis and verification

4. **Can human users remain meaningfully in control of multi-agent transactions?**
   - Users specify constraints at system startup
   - Constraints enforced at agent decision points
   - Agents cannot exceed budgets or ignore user requirements

### Experimental Variations

The framework supports multiple experimental configurations:

**1. Agent Autonomy Levels**
- **Full LLM:** Buyer makes all decisions via Claude AI
- **Constrained LLM:** Claude must respect hard constraints
- **Rule-based:** Deterministic agent behavior

**2. Protocol Strictness**
- **Strict BSPL:** All messages validated against protocol schema
- **Flexible:** Agents can send messages outside formal protocol

**3. Cost Control**
- **Unlimited:** No LLM call limits (costs may exceed budget)
- **Limited:** Hard caps on API calls and execution time

**4. Transparency Levels**
- **Full Logging:** Every LLM call logged with prompts/responses
- **Minimal Logging:** Only final decisions recorded

## Example Execution Trace

Here's what a complete transaction looks like:

```
[INITIALIZATION]
Buyer agent starting at 21:33:06
Loaded BSPL protocol with 3 roles: Buyer, Seller, Shipper
LLM initialized: claude-3-5-sonnet-20241022
Thresholds: 20 calls / 180 seconds

[USER INPUT]
Enter system requirements:
Budget: $20
Delivery: Raleigh, NC 27606
Product: pen

[QUOTE PHASE]
Status: 1 messages, 5s elapsed
→ Buyer sends RFQ_BUYER_001 (generic inquiry)

Status: 2 messages, 6s elapsed
← Seller quotes $5 for pen

Status: 3 messages, 7s elapsed
→ Buyer sends RFQ_A4BC9F8D_2133 (exploratory)

Status: 4 messages, 8s elapsed
← Seller quotes $4 for pen

[DECISION PHASE]
Status: 5 messages, 60s elapsed
→ Buyer evaluates both quotes against $20 budget
→ Buyer selects lower-priced quote ($4)
→ Buyer sends accept(RFQ_A4BC9F8D_2133, address='Raleigh, NC 27606')

[COMPLETION]
Status: 6 messages, 67s elapsed
← Seller confirms acceptance
← Shipper begins delivery logistics
→ Buyer confirms satisfaction

[TRANSACTION COMPLETED]
Total: 6 LLM-driven messages in 67 seconds
Final Cost: $4 item + shipping
Budget Remaining: ~$16
Delivery: Confirmed to Raleigh, NC 27606
```

## Troubleshooting

### Common Issues

**"Connection refused" error**
- Ensure all three agents are running in separate terminals
- Check that ports 8000, 8001, 8002 are not in use
- Try restarting all agents

**"API rate limit exceeded"**
- Wait a few minutes before retrying
- Reduce `max_calls` threshold to prevent rapid requests
- Use mock client for testing instead of production API

**"Protocol error: message not enabled"**
- The protocol rules don't allow this message in current state
- Check message history in debug logs
- Verify all required parameters are bound

**Agents hang or don't respond**
- Check debug logs for error messages
- Increase timeout in agent files if network is slow
- Verify agents are receiving messages (check network)

## References and Related Work

This project builds on:
- **BSPL (Blindingly Simple Protocol Language)** - Formal protocol specification framework
- **Claude AI (Anthropic)** - State-of-the-art large language model
- **Multi-Agent Systems Literature** - Agent coordination and collaboration patterns
- **Human-in-the-loop AI** - User oversight of autonomous agent decisions

For the full research paper, see: "Creating Human-in-the-loop Interaction Protocols, Ahoy!"

## Contributing

This is a research project. To contribute:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/your-feature`)
3. Implement changes with tests
4. Submit a pull request with description of changes

## License

See [LICENSE](LICENSE) file for details.

## Execution and Usage

### Quick Start

**Option 1: PowerShell Script (Recommended)**
```powershell
./start.ps1
```
This launches all three agents in separate terminal windows and coordinates their initialization.

**Option 2: Manual Terminal Execution**

Terminal 1 - Buyer Agent:
```bash
python agents/buyer.py
```

Terminal 2 - Seller Agent:
```bash
python agents/seller.py
```

Terminal 3 - Shipper Agent:
```bash
python agents/shipper.py
```

### User Interaction

When the Buyer agent starts, you'll be prompted to specify transaction requirements:

```
Enter system requirements:
- Budget constraint (optional): 20
- Delivery location (optional): Raleigh, NC 27606
- Product description (optional): pen
```

The Buyer agent will then:
1. Generate RFQs to the Seller
2. Receive and evaluate quotes
3. Compare options against constraints
4. Make intelligent purchasing decisions
5. Coordinate delivery through the Shipper
6. Report transaction completion

### Configuration

**Protocol Definition:** `protocols/purchase.bspl`
- Formal BSPL specification of all roles, messages, and rules
- Edit to modify protocol behavior or add new message types

**Agent Endpoints:** `configuration.py`
```python
AGENTS = {
    "Buyer": ("127.0.0.1", 8000),
    "Seller": ("127.0.0.1", 8001),
    "Shipper": ("127.0.0.1", 8002),
}
```

**LLM Configuration:** Set in `agents/buyer.py`
```python
llm_client = AnthropicLLMClient(model="claude-3-5-sonnet-20241022")
```

**Thresholds:** `lib/llm_client.py`
```python
initialize_llm_tracker(
    max_calls=20,           # Maximum LLM API calls
    max_time=3 * 60        # Maximum execution time (seconds)
)
```

### Monitoring Execution

**Console Output** shows minimal status:
```
Status: 0 messages, 0s elapsed
Status: 1 messages, 5s elapsed
Status: 2 messages, 8s elapsed
...
Status: 6 messages, 67s elapsed
[TRANSACTION COMPLETED]
```

**Debug Logs** in `logs/` directory provide detailed execution traces:
- Timestamp: `buyer_debug_20251215_213306.log`
- Full LLM prompts and responses
- Protocol state at each decision point
- Message enable/disable reasoning
- Constraint checking logic

Access debug logs while agents are running to understand decision-making:
```bash
tail -f logs/buyer_debug_*.log
```

## Project Structure

```
MAF/
├── agents/
│   ├── buyer.py                 # LLM-driven Buyer agent
│   ├── seller.py                # Rule-based Seller agent
│   └── shipper.py               # Rule-based Shipper agent
├── configuration.py             # Agent endpoints & protocol config
├── protocols/
│   └── purchase.bspl            # BSPL formal protocol specification
├── start.ps1                    # PowerShell launch script
├── start.sh                     # Bash launch script
│
├── lib/
│   ├── __init__.py
│   ├── agent_notes.py           # Agent decision logging
│   ├── llm_client.py            # Claude API & mock clients
│   ├── state_manager.py         # Protocol state serialization
│   ├── ui_manager.py            # Console & debug logging
│   └── utils.py                 # Shared utilities
│
├── logs/                       # Generated debug log files
│   ├── buyer_debug_*.log
│   ├── seller_debug_*.log
│   ├── shipper_debug_*.log
│   ├── agents.log              # Shared event log
│   └── agent_notes/
│       └── agent_notes.json   # Decision audit trail
│
├── debug_scripts/             # Testing utilities
│   └── test_agent_notes.py
│
├── __pycache__/               # Python cache
├── LICENSE
└── README.md                  # This file
```

## Key Design Principles

### 1. **Protocol-First Architecture**
- All agent communication follows the formal BSPL specification
- Protocol rules are enforced by the framework, not by agent code
- Message validation happens automatically

### 2. **LLM-Driven Decision Making**
- Agents use Claude AI to make intelligent decisions within constraints
- LLM context includes full protocol state and decision history
- Responses include reasoning for auditability

### 3. **Constraint Satisfaction**
- Budget constraints enforced before purchase commitment
- Delivery verification required before accepting offers
- Transparent cost breakdowns provided to user

### 4. **Complete Auditability**
- Every decision is logged with full reasoning
- LLM prompts and responses recorded
- Protocol state snapshots at each step
- Enables reproduction and debugging of agent behavior

### 5. **Resource Management**
- LLM call limits prevent runaway costs
- Time limits ensure predictable execution
- Graceful termination when thresholds exceeded
- Clear user communication of constraint violations

## Advanced Usage

### Testing with Mock LLM

For development without API costs:

```python
from lib.llm_client import MockLLMClient, initialize_llm_tracker

llm_client = MockLLMClient()  # Instead of AnthropicLLMClient
initialize_llm_tracker(max_calls=50, max_time=60*10)
```

### Analyzing Decision Logs

The agent notes JSON file provides structured decision data:

```bash
# View decision audit trail
cat logs/agent_notes/agent_notes.json | python -m json.tool
```

### Extending the Protocol

To add new message types or modify the protocol:

1. Edit `protocols/purchase.bspl` with new message definitions
2. Update agent logic to handle new message types
3. Modify `configuration.py` if role changes required
4. Test with mock client first before using production API

