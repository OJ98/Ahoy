#!/usr/bin/env python3
"""
CHIPS - Conversational Interface for Protocol and Input Setup
An intelligent interface that converses with the user to infer protocol/role,
then generates input.txt based on the conversation. Uses LLM for inference.
"""

import asyncio
import sys
import tempfile
import json
from pathlib import Path
from typing import Tuple, Optional, List

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.protocol_discovery import (
    get_all_protocols,
    get_protocol_structure,
    get_protocol_summary_for_llm,
    validate_protocol_and_role,
)
from lib.llm_client import AnthropicLLMClient


class CHIPS:
    """Intelligent conversational interface for protocol and role selection."""
    
    def __init__(self):
        self.protocol: Optional[str] = None
        self.role: Optional[str] = None
        self.roles_list: List[Tuple[str, str]] = []  # List of (protocol, role) tuples
        self.conversation: str = ""
        self.llm_client = AnthropicLLMClient()
        self.protocols = get_all_protocols()
    
    def print_welcome(self):
        """Display welcome message."""
        print("\n" + "="*70, flush=True)
        print("CHIPS - Conversational Interface for Protocol & Role Setup", flush=True)
        print("="*70, flush=True)
        print("\nHello! I'm CHIPS. I'll help you set up ahoy for a multi-agent scenario.", flush=True)
        print("Tell me what you'd like to accomplish, and I'll infer the right", flush=True)
        print("protocol and role for ahoy to play.\n", flush=True)
    
    def gather_scenario(self) -> str:
        """Gather user's scenario description through conversation."""
        print("Describe the scenario or goal you'd like ahoy to participate in.", flush=True)
        print("(Enter multiple lines. Type 'END' on a new line to finish)\n", flush=True)
        
        lines = []
        try:
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
        except KeyboardInterrupt:
            print("\nSetup cancelled.", flush=True)
            sys.exit(0)
        
        scenario = "\n".join(lines).strip()
        return scenario if scenario else "Execute the protocol successfully."
    
    async def infer_protocol_and_role(self, scenario: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Use LLM to infer protocol and role(s) from user's scenario description.
        Can return single or multiple roles.
        
        Args:
            scenario: User's scenario description
        
        Returns:
            Tuple of (protocol_name, role_name) or (None, None) on failure
            Note: For multiple roles, this returns the primary role; see infer_protocol_and_roles_list() for all roles
        """
        roles_list = await self.infer_protocol_and_roles_list(scenario)
        if roles_list:
            protocol, role = roles_list[0]
            return protocol, role
        return None, None
    
    async def infer_protocol_and_roles_list(self, scenario: str) -> List[Tuple[str, str]]:
        """
        Use LLM to infer protocol and role(s) from user's scenario description.
        Returns all roles identified by the LLM.
        
        Args:
            scenario: User's scenario description
        
        Returns:
            List of (protocol_name, role_name) tuples, or empty list on failure
        """
        print("\n" + "="*70, flush=True)
        print("Analyzing scenario with LLM...", flush=True)
        print("="*70 + "\n", flush=True)
        
        try:
            # Get protocol summary for LLM context
            protocol_summary = get_protocol_summary_for_llm()
            
            # Create prompt for LLM to infer protocol(s) and role(s)
            prompt = f"""You are a protocol selection assistant. Based on the user's goal, 
determine which protocol(s) and role(s) the agent (ahoy) should play in.

Note: Return ONLY the role(s) that ahoy should directly play. Other agents will handle their own roles.
Return multiple roles only if the scenario explicitly suggests the agent should play multiple distinct roles
(e.g., coordinating across protocols, or multi-protocol participation). For a simple single-protocol scenario,
return just the one primary role.

{protocol_summary}

User's Goal:
{scenario}

Respond with ONLY the protocol(s) and role(s) in this exact format:
PROTOCOL: <ProtocolName>
ROLE: <RoleName>

Repeat PROTOCOL/ROLE pairs only if multiple distinct roles are needed. Be concise. Do not explain your reasoning."""
            
            # Call LLM
            response = await self.llm_client.complete(prompt, max_tokens=200)
            
            # Parse response - extract all PROTOCOL/ROLE pairs
            roles_list = []
            lines = response.strip().split('\n')
            
            i = 0
            while i < len(lines):
                line = lines[i].strip()
                if line.startswith('PROTOCOL:'):
                    protocol_name = line.replace('PROTOCOL:', '').strip()
                    # Look for corresponding ROLE in next line
                    if i + 1 < len(lines):
                        role_line = lines[i + 1].strip()
                        if role_line.startswith('ROLE:'):
                            role_name = role_line.replace('ROLE:', '').strip()
                            
                            # Validate
                            is_valid, error_msg = validate_protocol_and_role(protocol_name, role_name)
                            if is_valid:
                                roles_list.append((protocol_name, role_name))
                            else:
                                print(f"⚠ Skipped invalid role: {error_msg}", flush=True)
                            
                            i += 2
                            continue
                i += 1
            
            if roles_list:
                roles_str = ", ".join([f"{p}:{r}" for p, r in roles_list])
                print(f"✓ LLM inferred: {roles_str}\n", flush=True)
                return roles_list
            else:
                print("✗ Could not parse LLM response", flush=True)
                return []
            
        except Exception as e:
            print(f"✗ Error during LLM inference: {e}", flush=True)
            return []
    
    def confirm_selection(self, protocol: str, role: str) -> bool:
        """Confirm the LLM's protocol and role selection."""
        print(f"{'='*70}", flush=True)
        print("LLM Inference Result", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"Protocol: {protocol}", flush=True)
        print(f"Role: {role}", flush=True)
        print(f"Scenario:\n{self.conversation}\n", flush=True)
        
        while True:
            response = input("Does this look correct? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            else:
                print("Please enter 'yes' or 'no'.", flush=True)
    
    def show_protocol_options(self) -> Tuple[Optional[str], Optional[str]]:
        """Show available protocols for manual selection."""
        print(f"\n{'='*70}", flush=True)
        print("Available Protocols", flush=True)
        print(f"{'='*70}\n", flush=True)
        
        protocol_list = list(self.protocols.keys())
        for i, proto in enumerate(protocol_list, 1):
            structure = get_protocol_structure(proto)
            roles_str = ", ".join(structure["roles"]) if structure else ""
            print(f"{i}. {proto}: [{roles_str}]", flush=True)
        
        while True:
            try:
                choice = input("\nSelect a protocol (number or name): ").strip()
                
                # Numeric choice
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(protocol_list):
                        protocol = protocol_list[idx]
                        break
                # Name match
                elif choice in protocol_list:
                    protocol = choice
                    break
                else:
                    print(f"Invalid choice. Enter 1-{len(protocol_list)} or a protocol name.", flush=True)
                    continue
            except (KeyboardInterrupt, ValueError):
                print("\nSetup cancelled.", flush=True)
                sys.exit(0)
        
        # Select role
        structure = get_protocol_structure(protocol)
        roles = structure["roles"] if structure else []
        
        print(f"\nAvailable roles in {protocol}: {', '.join(roles)}", flush=True)
        while True:
            try:
                role = input(f"Select a role (number or name): ").strip()
                
                # Numeric choice
                if role.isdigit():
                    idx = int(role) - 1
                    if 0 <= idx < len(roles):
                        role = roles[idx]
                        break
                # Name match
                elif role in roles:
                    break
                else:
                    print(f"Invalid choice. Enter 1-{len(roles)} or a role name.", flush=True)
                    continue
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                sys.exit(0)
        
        return protocol, role
    
    def write_config_file(self) -> bool:
        """Write the protocol:role config to temp file for ahoy to read.
        
        Supports both single role (backward compatible) and multiple roles.
        Single role: "Protocol:Role"
        Multiple roles: JSON format with list of {protocol, role} objects
        """
        try:
            config_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
            
            # Use single-role format for backward compatibility if only one role
            if len(self.roles_list) == 1:
                protocol, role = self.roles_list[0]
                config_file.write_text(f"{protocol}:{role}")
            else:
                # Use JSON format for multiple roles
                config_data = {
                    "roles": [{"protocol": p, "role": r} for p, r in self.roles_list]
                }
                config_file.write_text(json.dumps(config_data))
            
            print(f"✓ Config file written: {config_file}")
            return True
        except Exception as e:
            print(f"✗ Error writing config file: {e}")
            return False
    
    def write_input_file(self) -> bool:
        """Write the input.txt file with user scenario."""
        try:
            input_file = PROJECT_ROOT / "input.txt"
            input_file.write_text(self.conversation)
            print(f"✓ Input file written: {input_file}")
            return True
        except Exception as e:
            print(f"✗ Error writing input file: {e}")
            return False
    
    async def run(self):
        """Run the CHIPS interface."""
        self.print_welcome()
        
        # Gather scenario
        self.conversation = self.gather_scenario()
        
        # Infer protocol and role(s)
        roles_list = await self.infer_protocol_and_roles_list(self.conversation)
        
        # If inference failed, offer manual selection
        if not roles_list:
            print("\n⚠ LLM inference didn't work. Let's try manual selection.\n", flush=True)
            protocol, role = self.show_protocol_options()
            roles_list = [(protocol, role)]
        
        self.roles_list = roles_list
        if roles_list:
            self.protocol = roles_list[0][0]
            self.role = roles_list[0][1]
        
        # Ask if user wants to add more roles
        self.roles_list = await self._ask_for_additional_roles(self.roles_list)
        
        # Confirm selection
        while not self._confirm_all_selections():
            print("\nLet's try a different scenario.\n", flush=True)
            self.conversation = self.gather_scenario()
            protocol, role = await self.infer_protocol_and_role(self.conversation)
            
            if not protocol or not role:
                protocol, role = self.show_protocol_options()
            
            self.protocol = protocol
            self.role = role
            self.roles_list = [(protocol, role)]
            self.roles_list = await self._ask_for_additional_roles(self.roles_list)
        
        # Write files
        print(f"\n{'='*70}", flush=True)
        print("Writing configuration files...", flush=True)
        print(f"{'='*70}\n", flush=True)
        
        config_ok = self.write_config_file()
        input_ok = self.write_input_file()
        
        if config_ok and input_ok:
            print(f"\n{'='*70}", flush=True)
            print("✅ Setup complete!", flush=True)
            print(f"{'='*70}", flush=True)
            roles_str = ", ".join([f"{p}:{r}" for p, r in self.roles_list])
            print(f"\nConfiguration saved for: {roles_str}", flush=True)
            print(f"  - Protocol/Role: {Path(tempfile.gettempdir()) / 'maf_chips_config.txt'}", flush=True)
            print(f"  - Scenario: {PROJECT_ROOT / 'input.txt'}", flush=True)
            print("\nYou can now run: ./start.ps1 (or ./start.sh on Unix)", flush=True)
            print("to start ahoy and the other agents.\n", flush=True)
        else:
            print("\n❌ Setup failed. Some files could not be written.", flush=True)
            sys.exit(1)
    
    async def _ask_for_additional_roles(self, roles_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Ask user if they want to add more roles for multi-protocol support."""
        print(f"\n{'='*70}", flush=True)
        print("Multi-Protocol Support", flush=True)
        print(f"{'='*70}", flush=True)
        print(f"\nCurrent roles: {', '.join([f'{p}:{r}' for p, r in roles_list])}", flush=True)
        
        while True:
            response = input("\nWould you like to add another protocol/role? (yes/no): ").strip().lower()
            if response in ('no', 'n'):
                break
            elif response in ('yes', 'y'):
                protocol, role = self.show_protocol_options()
                if (protocol, role) not in roles_list:
                    roles_list.append((protocol, role))
                    print(f"✓ Added {protocol}:{role}", flush=True)
                    print(f"  Current roles: {', '.join([f'{p}:{r}' for p, r in roles_list])}", flush=True)
                else:
                    print(f"⚠ {protocol}:{role} already in list", flush=True)
            else:
                print("Please enter 'yes' or 'no'.", flush=True)
        
        return roles_list
    
    def _confirm_all_selections(self) -> bool:
        """Confirm all selected roles."""
        print(f"\n{'='*70}", flush=True)
        print("Configuration Summary", flush=True)
        print(f"{'='*70}", flush=True)
        for i, (protocol, role) in enumerate(self.roles_list, 1):
            print(f"{i}. {protocol}:{role}", flush=True)
        print(f"\nScenario:\n{self.conversation}\n", flush=True)
        
        while True:
            response = input("Is this correct? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            else:
                print("Please enter 'yes' or 'no'.", flush=True)


if __name__ == "__main__":
    chips = CHIPS()
    asyncio.run(chips.run())
