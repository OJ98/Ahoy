# CHiPs-Ahoy
This repository contains the code associated with the paper "Creating Human-in-the-loop Interaction Protocols, Ahoy!"

## Project Overview

CHiPs-Ahoy is a multi-agent system that implements a **Purchase Protocol** using BSPL (Business Protocol Specification Language). The system demonstrates how LLM-driven agents can collaborate through structured communication protocols to execute complex multi-party transactions.

### Key Technologies
- **BSPL Protocol Framework:** Formal specification of multi-agent communication
- **Claude AI (Anthropic):** LLM backbone for agent decision-making
- **Python Async:** Concurrent agent execution with asyncio
- **Network Communication:** TCP/IP sockets for inter-agent messaging

## Protocol: Purchase

The Purchase Protocol defines a three-party transaction involving:

1. **Buyer** - Requests quotes and makes purchasing decisions
2. **Seller** - Provides pricing and fulfills accepted orders
3. **Shipper** - Handles delivery logistics

### Message Flow

```
Buyer → Seller:    rfq [Request for Quote]
Seller → Buyer:    quote [Price quote response]
Buyer → Seller:    accept OR reject [Purchase decision]
Seller → Shipper:  ship [Shipping instruction]
Shipper → Buyer:   deliver [Delivery confirmation]
```

### Protocol State Parameters
- **ID** (key): Unique transaction identifier
- **item**: Product being purchased
- **price**: Negotiated price
- **address**: Delivery address
- **outcome**: Transaction result (delivered/rejected)
- **shipped**: Shipping confirmation status

## System Architecture

### Agent Configuration

Each agent runs as a separate process with dedicated network endpoints:

```
Buyer:   127.0.0.1:8000
Seller:  127.0.0.1:8001
Shipper: 127.0.0.1:8002
```

### Core Components

#### 1. **LLM-Driven Agents** (`buyer.py`, `seller.py`, `shipper.py`)
- **Buyer:** Uses Claude AI to intelligently analyze quotes and make purchasing decisions
- **Seller:** Responds with dynamic pricing and fulfillment
- **Shipper:** Manages delivery logistics

#### 2. **BSPL Adapter** (`configuration.py`)
- Loads the Purchase protocol specification from `purchase.bspl`
- Manages protocol state and message validation
- Routes messages between agents according to protocol rules

#### 3. **LLM Integration** (`lib/llm_client.py`)
- `AnthropicLLMClient`: Production client for Claude API
- `MockLLMClient`: Testing client with fixed responses
- Automatic tracking of LLM calls with configurable limits
- Timeout handling and response parsing

#### 4. **Agent State Management** (`lib/state_manager.py`)
- Extracts and serializes protocol state for LLM context
- Manages social state (bindings, message history, context)
- Provides structured context about current protocol execution

#### 5. **UI and Logging** (`lib/ui_manager.py`)
- Dual logging: Debug file output + console status updates
- Formatted messages for protocol events
- Minimal status displays for user feedback
- Error handling and transaction summaries

#### 6. **Utilities** (`lib/utils.py`)
- Graceful shutdown management
- Message history construction
- User prompt generation with protocol context
- Requirement gathering from users

## Features

### LLM Call Tracking and Threshold Enforcement
The system includes automatic tracking of LLM calls with graceful termination when either of two thresholds is exceeded:
- **Call Limit:** 20 LLM calls
- **Time Limit:** 3 minutes (180 seconds)

Whichever threshold is reached first will trigger graceful program termination.

### Minimal Status Updates
After each LLM call, the UI displays minimal status information showing:
- Number of messages sent (LLM calls made)
- Time elapsed since initialization

Status format: `📊 N messages, Xs elapsed`

### Graceful Termination
When a threshold is exceeded, the program will:
1. Log the threshold reason to the debug log
2. Display an error message to the user
3. Properly close all file handlers
4. Terminate without hanging processes

## Implementation Details

### LLM Call Tracking (`lib/llm_client.py`)
- `LLMCallTracker` class monitors calls and elapsed time
- `initialize_llm_tracker()` - Initialize with custom thresholds
- `get_llm_tracker()` - Access the current tracker
- Both `AnthropicLLMClient` and `MockLLMClient` automatically track calls

### UI Updates (`lib/ui_manager.py`)
- `UserInterface.status_update()` - Display minimal status with message count and elapsed time

### Threshold Checking (`buyer.py`)
- Tracker initialized at program start
- Thresholds checked before and after each LLM call
- Graceful exit via `SystemExit` exception when thresholds are exceeded

## Execution

### Running the System

1. **Start all agents in separate terminals:**
   ```bash
   python buyer.py
   python seller.py
   python shipper.py
   ```

   Or use the provided script:
   ```bash
   ./start.ps1
   ```

2. **Follow the Buyer agent prompts** to enter system requirements

3. **Monitor debug logs** in the `logs/` directory

4. **View status updates** showing LLM call count and elapsed time

### Configuration

- Protocol specification: `purchase.bspl`
- Agent endpoints: `configuration.py`
- LLM timeouts: `TIMEOUT = 30.0` (in agent files)
- Thresholds: 20 calls / 3 minutes (customizable in `initialize_llm_tracker()`)

## Project Structure

```
.
├── buyer.py                 # LLM-driven Buyer agent
├── seller.py               # Simple Seller agent
├── shipper.py              # Simple Shipper agent
├── configuration.py        # Protocol and agent configuration
├── purchase.bspl           # BSPL protocol specification
├── start.ps1               # Script to launch all agents
├── lib/
│   ├── __init__.py
│   ├── llm_client.py       # LLM integration & call tracking
│   ├── ui_manager.py       # Console UI & logging
│   ├── state_manager.py    # Protocol state serialization
│   └── utils.py            # Utilities & helpers
├── logs/                   # Debug log files (generated)
└── README.md
```

## Debug and Logging

Each agent generates timestamped debug logs in the `logs/` directory with format: `{agent}_debug_{YYYYMMDD_HHMMSS}.log`

Debug logs contain:
- Full LLM prompts and responses
- Protocol state snapshots
- Message enable/disable reasoning
- Threshold status checks
- Error traces

Console output shows:
- Minimal status updates (message count + elapsed time)
- Error messages
- Transaction completion summary

