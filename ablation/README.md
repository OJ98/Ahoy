# Ablation Study: Information Sources for Protocol-Based LLM Agents

This directory contains an ablation study comparing three variants of the AHOY system to isolate the value of two information sources:

## Baselines

### Baseline 0: Full AHOY (Reference)
**Location**: `baseline0_full/`

The full system with:
- BSPL protocol definitions with inline **message comments** explaining each message's purpose
- **Enabled set filtering**: LLM only sees messages that are currently valid under protocol constraints

### Baseline 1: No Message Comments
**Location**: `baseline1_no_comments/`

Same as Full AHOY, except:
- BSPL protocol definitions have **inline comments stripped** (no `//` comment lines)
- LLM still sees **enabled set filtering** (only valid messages)
- **Hypothesis**: Message comments aid comprehension and reduce invalid message selection

### Baseline 2: No Filtering (Exception-Driven Learning)
**Location**: `baseline2_no_filtering/`

Different decision mechanism:
- BSPL protocol definitions shown **in full**
- LLM sees **ALL possible messages** in the protocol (no enabled set filtering)
- **Exception handling**: When agent attempts invalid message, kiko raises exception
- LLM receives **exception feedback** in next decision cycle, learning constraints through trial-and-error
- **Hypothesis**: Exception-driven learning is sufficient; filtering is not necessary

## Measurement

All three baselines execute identical transaction scenarios and collect:
- **Accuracy**: % of chosen messages that are valid (protocol-compliant)
- **Exception Count**: Frequency of kiko constraint violations (mainly for Baseline 2)
- **Transaction Success**: Whether agents complete all required protocol steps
- **Latency**: Decision time per message choice
- **Recovery Pattern**: Whether exceptions lead to corrected next decisions

## Running the Study

```bash
# Run all three baselines on Purchase and Logistics protocols (3 runs each)
python run_ablation.py --protocols Purchase Logistics --runs 3

# Run specific baseline only
python run_ablation.py --baselines baseline1_no_comments --protocols Purchase --runs 1

# Analyze results after running
python analyze_results.py
```

## Results

Results are stored in:
```
logs/ablation/
├── baseline0_full/
├── baseline1_no_comments/
└── baseline2_no_filtering/
```

Each baseline folder contains:
- `agent_*.log` - Detailed agent execution logs
- `metrics.json` - Aggregated metrics for the run
- `transactions.json` - Transaction-level details (success, accuracy, exceptions)

## Key Implementation Details

- **No changes to core**: All baseline variants reuse `lib/` and `agents/` code
- **Isolated variants**: Each baseline has its own `ahoy.py` that uses variant utilities
- **Metrics tracking**: Special logging in each variant to track accuracy and exceptions
- **Minimal code duplication**: Variants only override the specific functions that differ
