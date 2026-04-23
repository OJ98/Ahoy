#!/usr/bin/env python3
"""
Baseline 1 variant: No Message Comments

Overrides `_include_protocol_definitions()` from lib/utils.py to strip
inline comments from BSPL files before showing to the LLM.

The enabled set filtering remains in place.
"""

from pathlib import Path
from typing import Dict


def include_protocol_definitions_no_comments() -> str:
    """
    Load all BSPL protocol definitions but strip inline comments.
    
    This is a variant of lib/utils.py's _include_protocol_definitions()
    that removes all lines starting with '//' to test whether message
    comments aid comprehension.
    
    Returns:
        Formatted string with protocol definitions (comments removed)
    """
    protocols_dir = Path(__file__).resolve().parent.parent.parent / "protocols"
    
    protocol_section = "\n\n" + "=" * 70 + "\n"
    protocol_section += "PROTOCOL DEFINITIONS (BSPL specs - COMMENTS REMOVED FOR THIS VARIANT):\n"
    protocol_section += "=" * 70 + "\n\n"
    
    bspl_files = sorted(protocols_dir.glob("*.bspl"))
    
    if not bspl_files:
        return protocol_section + "(No BSPL protocol files found)\n"
    
    for bspl_file in bspl_files:
        try:
            with open(bspl_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
                # Filter out comment lines (lines starting with // or containing only //)
                filtered_lines = [
                    line for line in lines
                    if not line.strip().startswith('//')
                ]
                content = "".join(filtered_lines).strip()
                
                protocol_name = bspl_file.stem
                protocol_section += f"\n--- {protocol_name.upper()} PROTOCOL ---\n\n"
                protocol_section += content + "\n"
        except Exception as e:
            protocol_section += f"\n(Error reading {bspl_file.name}: {e})\n"
    
    protocol_section += "\n" + "=" * 70 + "\n"
    return protocol_section
