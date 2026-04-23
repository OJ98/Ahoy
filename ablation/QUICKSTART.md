# Quick Start Guide: Running the Ablation Study

## Prerequisites

**Important**: The ablation study requires the `maf-py` conda environment.

```bash
# Activate the environment FIRST
conda activate maf-py

# Then navigate to the project root
cd c:\PhD\Research\MultiAgents\Code\MAF
```

If you don't have the environment set up:
```bash
conda env create -f environment.yml -n maf-py
conda activate maf-py
```

This directory contains the ablation study for the AHOY system, testing the independent contribution of:
1. **Message Comments** - Inline explanations in BSPL protocol files
2. **Enabled Set Filtering** - Protocol-valid messages only (vs. all messages)

## Directory Structure

```
ablation/
├── README.md                      # Full documentation
├── __init__.py                    # Python package init
├── ablation_config.py             # Metrics tracking and baseline detection
├── run_ablation.py               # Harness to execute all baselines
├── analyze_results.py            # Results analyzer
├── QUICKSTART.md                 # This file
│
├── baseline0_full/               # Full AHOY (reference)
│   ├── ahoy.py                  # Wrapper to main agents/ahoy.py
│   └── __init__.py
│
├── baseline1_no_comments/        # No message comments
│   ├── ahoy.py                  # Variant with comment stripping
│   ├── utils_variant.py         # Comment removal utility
│   └── __init__.py
│
└── baseline2_no_filtering/       # Exception-driven learning
    ├── ahoy.py                  # Variant with all-messages + exception tracking
    ├── utils_variant.py         # Exception tracking utility
    └── __init__.py
```

## Running the Study

### Option 1: Using Launcher Script (Recommended)

The launcher scripts automatically activate the maf-py environment:

**Windows:**
```bash
ablation\run_ablation.bat --all --runs 1
```

**macOS/Linux:**
```bash
bash ablation/run_ablation.sh --all --runs 1
```

### Option 2: Manual Environment Activation

```bash
# Activate environment first
conda activate maf-py

# Then run the harness
cd c:\PhD\Research\MultiAgents\Code\MAF
python ablation/run_ablation.py --all --runs 1
```

### Option 3: Run All Baselines (Recommended First Run)

```bash
cd c:\PhD\Research\MultiAgents\Code\MAF
python ablation/run_ablation.py --all --runs 1
```

This will:
1. Run baseline0_full on Purchase and Logistics protocols (1 run each)
2. Run baseline1_no_comments on Purchase and Logistics protocols (1 run each)
3. Run baseline2_no_filtering on Purchase and Logistics protocols (1 run each)
4. Total: 6 transactions, ~5-10 minutes

### Option 4: Run Specific Baselines

```bash
# Only baseline 1 (no comments)
python ablation/run_ablation.py --baselines baseline1_no_comments --protocols Purchase --runs 3

# Multiple baselines, single protocol
python ablation/run_ablation.py --baselines baseline0_full baseline1_no_comments --protocols Purchase --runs 2

# Specific baselines and protocols
python ablation/run_ablation.py --baselines baseline0_full baseline2_no_filtering --protocols Purchase Logistics --runs 1
```

### Option 5: Manual Single Baseline Run

To run a single baseline directly:

```bash
# Run baseline 0 manually
cd ablation/baseline0_full
python ahoy.py

# Run baseline 1 manually
cd ablation/baseline1_no_comments
python ahoy.py

# Run baseline 2 manually
cd ablation/baseline2_no_filtering
python ahoy.py
```

## Analyzing Results

After running the study:

```bash
python ablation/analyze_results.py
```

This generates:
- `logs/ablation/analysis_report.txt` - Human-readable findings
- `logs/ablation/analysis_metrics.json` - Detailed metrics in JSON format
- Console output with comparative statistics

## What to Expect

### Baseline 0 (Full)
- **Accuracy**: High (LLM sees enabled messages + explanatory comments)
- **Exceptions**: None (only valid messages shown)
- **Completion**: Should complete most transactions

### Baseline 1 (No Comments)
- **Accuracy**: Potentially lower (LLM must infer message purpose from context)
- **Exceptions**: None (still has enabled filtering)
- **Completion**: May have more invalid attempts vs Baseline 0
- **Expected difference**: ~5-15% lower accuracy

### Baseline 2 (No Filtering)
- **Accuracy**: May be lower initially (LLM sees all messages, must learn constraints)
- **Exceptions**: Multiple (LLM attempts invalid messages, learns from feedback)
- **Completion**: Depends on whether exception-driven learning is sufficient
- **Expected difference**: Higher exception count, potentially lower initial accuracy

## Example Output

```
======================================================================
ABLATION STUDY - Multi-Baseline Comparison
======================================================================
Baselines: baseline0_full, baseline1_no_comments, baseline2_no_filtering
Protocols: Purchase, Logistics
Runs per protocol: 1
======================================================================

[1/6] Starting baseline0_full on Purchase...

[RUN 1] baseline0_full → Purchase:Buyer
✓ Completed

[2/6] Starting baseline0_full on Logistics...

[RUN 1] baseline0_full → Logistics:Wrapper
✓ Completed

...

======================================================================
Ablation study complete!
Results saved to: c:\PhD\Research\MultiAgents\Code\MAF\logs\ablation
```

## Results Structure

After running, you'll have:

```
logs/ablation/
├── baseline0_full/
│   ├── Purchase_Buyer_run1.log
│   ├── Logistics_Wrapper_run1.log
│   └── transactions.json         # Metrics for all runs
├── baseline1_no_comments/
│   ├── Purchase_Buyer_run1.log
│   ├── Logistics_Wrapper_run1.log
│   └── transactions.json
├── baseline2_no_filtering/
│   ├── Purchase_Buyer_run1.log
│   ├── Logistics_Wrapper_run1.log
│   └── transactions.json
├── summary.json                  # High-level summary
├── analysis_metrics.json         # Comparative metrics
└── analysis_report.txt          # Human-readable findings
```

## Key Metrics

Each transaction records:
- **accuracy_score**: % of chosen messages that were valid (0.0-1.0)
- **exception_count**: Number of protocol violations (mainly for Baseline 2)
- **total_decisions**: How many times the LLM was consulted
- **success**: Whether the transaction completed
- **duration_seconds**: Wall-clock time for transaction

## Troubleshooting

### Agent Fails to Start
- Make sure you're in the project root directory
- Check that `input.txt` exists (contains agent instructions)
- Verify conda environment is activated: `conda activate maf-py`

### Metrics Not Collected
- Check `logs/ablation/baseline*/transactions.json` exists
- Run `analyze_results.py` to aggregate available metrics

### Baseline 2 Keeps Trying Same Invalid Message
- This is expected behavior in exception-driven learning
- The LLM may need multiple attempts to learn constraints
- Long transactions are normal for this baseline

## Next Steps

1. **Compare results** using the analysis report
2. **Adjust runs** if needed (e.g., increase num_runs for more data)
3. **Extract findings** from `analysis_metrics.json` for your paper
4. **Fine-tune baselines** if needed (e.g., adjust exception feedback format)

## Questions or Issues?

Check the main README.md for more detailed documentation about each baseline.
