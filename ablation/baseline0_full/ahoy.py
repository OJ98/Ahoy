#!/usr/bin/env python3
"""
Baseline 0: Full AHOY (Reference)

This is the standard AHOY agent with:
- BSPL protocol definitions including inline comments
- Enabled set filtering (only protocol-valid messages shown to LLM)

This serves as the reference baseline for the ablation study.
"""

import sys
from pathlib import Path

# Add parent directories to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Set ablation mode environment variable
import os
os.environ["ABLATION_MODE"] = "baseline0_full"

# Import and run the standard ahoy agent
# (This ensures we're using the production version without modifications)
from agents.ahoy import main, adapter, llm_client, ui

if __name__ == "__main__":
    try:
        # Run standard ahoy main
        import asyncio
        asyncio.run(main())
    except KeyboardInterrupt:
        ui.message("Baseline 0 (Full) interrupted by user")
    except SystemExit as e:
        # Let completion signals propagate
        raise
    except Exception as e:
        ui.error_occurred(str(e))
        raise
