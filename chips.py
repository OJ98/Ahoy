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
        print("\n" + "="*70)
        print("CHIPS - Conversational Interface for Protocol & Role Setup")
        print("="*70)
        print("\nHello! I'm CHIPS. I'll help you set up ahoy for a multi-agent scenario.")
        print("Tell me what you'd like to accomplish, and I'll infer the right")
        print("protocol and role for ahoy to play.\n")
    
    def gather_scenario(self) -> str:
        """Gather user's scenario description through conversation."""
        print("Describe the scenario or goal you'd like ahoy to participate in.")
        print("(Enter multiple lines. Type 'END' on a new line to finish)\n")
        
        lines = []
        try:
            while True:
                line = input()
                if line.strip().upper() == "END":
                    break
                lines.append(line)
        except KeyboardInterrupt:
            print("\nSetup cancelled.")
            sys.exit(0)
        
        scenario = "\n".join(lines).strip()
        return scenario if scenario else "Execute the protocol successfully."
    
    async def infer_protocol_and_role(self, scenario: str) -> Tuple[Optional[str], Optional[str]]:
        """
        Use LLM to infer protocol and role from user's scenario description.
        
        Args:
            scenario: User's scenario description
        
        Returns:
            Tuple of (protocol_name, role_name) or (None, None) on failure
        """
        print("\n" + "="*70)
        print("Analyzing scenario with LLM...")
        print("="*70 + "\n")
        
        try:
            # Get protocol summary for LLM context
            protocol_summary = get_protocol_summary_for_llm()
            
            # Create prompt for LLM to infer protocol and role
            prompt = f"""You are a protocol selection assistant. Based on the user's goal, 
determine which protocol and role ahoy should participate in.

{protocol_summary}

User's Goal:
{scenario}

Respond with ONLY the protocol and role in this exact format:
PROTOCOL: <ProtocolName>
ROLE: <RoleName>

Be concise. Do not explain your reasoning."""
            
            # Call LLM
            response = await self.llm_client.complete(prompt, max_tokens=100)
            
            # Parse response
            protocol_name = None
            role_name = None
            
            for line in response.strip().split('\n'):
                if line.startswith('PROTOCOL:'):
                    protocol_name = line.replace('PROTOCOL:', '').strip()
                elif line.startswith('ROLE:'):
                    role_name = line.replace('ROLE:', '').strip()
            
            # Validate
            if protocol_name and role_name:
                is_valid, error_msg = validate_protocol_and_role(protocol_name, role_name)
                if is_valid:
                    print(f"✓ LLM inferred: {protocol_name}:{role_name}\n")
                    return protocol_name, role_name
                else:
                    print(f"✗ LLM selection invalid: {error_msg}")
                    return None, None
            
            print("✗ Could not parse LLM response")
            return None, None
            
        except Exception as e:
            print(f"✗ Error during LLM inference: {e}")
            return None, None
    
    def confirm_selection(self, protocol: str, role: str) -> bool:
        """Confirm the LLM's protocol and role selection."""
        print(f"{'='*70}")
        print("LLM Inference Result")
        print(f"{'='*70}")
        print(f"Protocol: {protocol}")
        print(f"Role: {role}")
        print(f"Scenario:\n{self.conversation}\n")
        
        while True:
            response = input("Does this look correct? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            else:
                print("Please enter 'yes' or 'no'.")
    
    def show_protocol_options(self) -> Tuple[Optional[str], Optional[str]]:
        """Show available protocols for manual selection."""
        print(f"\n{'='*70}")
        print("Available Protocols")
        print(f"{'='*70}\n")
        
        protocol_list = list(self.protocols.keys())
        for i, proto in enumerate(protocol_list, 1):
            structure = get_protocol_structure(proto)
            roles_str = ", ".join(structure["roles"]) if structure else ""
            print(f"{i}. {proto}: [{roles_str}]")
        
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
                    print(f"Invalid choice. Enter 1-{len(protocol_list)} or a protocol name.")
                    continue
            except (KeyboardInterrupt, ValueError):
                print("\nSetup cancelled.")
                sys.exit(0)
        
        # Select role
        structure = get_protocol_structure(protocol)
        roles = structure["roles"] if structure else []
        
        print(f"\nAvailable roles in {protocol}: {', '.join(roles)}")
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
                    print(f"Invalid choice. Enter 1-{len(roles)} or a role name.")
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
        
        # Infer protocol and role
        protocol, role = await self.infer_protocol_and_role(self.conversation)
        
        # If inference failed, offer manual selection
        if not protocol or not role:
            print("\n⚠ LLM inference didn't work. Let's try manual selection.\n")
            protocol, role = self.show_protocol_options()
        
        self.protocol = protocol
        self.role = role
        self.roles_list = [(protocol, role)]
        
        # Ask if user wants to add more roles
        self.roles_list = await self._ask_for_additional_roles(self.roles_list)
        
        # Confirm selection
        while not self._confirm_all_selections():
            print("\nLet's try a different scenario.\n")
            self.conversation = self.gather_scenario()
            protocol, role = await self.infer_protocol_and_role(self.conversation)
            
            if not protocol or not role:
                protocol, role = self.show_protocol_options()
            
            self.protocol = protocol
            self.role = role
            self.roles_list = [(protocol, role)]
            self.roles_list = await self._ask_for_additional_roles(self.roles_list)
        
        # Write files
        print(f"\n{'='*70}")
        print("Writing configuration files...")
        print(f"{'='*70}\n")
        
        config_ok = self.write_config_file()
        input_ok = self.write_input_file()
        
        if config_ok and input_ok:
            print(f"\n{'='*70}")
            print("✅ Setup complete!")
            print(f"{'='*70}")
            roles_str = ", ".join([f"{p}:{r}" for p, r in self.roles_list])
            print(f"\nConfiguration saved for: {roles_str}")
            print(f"  - Protocol/Role: {Path(tempfile.gettempdir()) / 'maf_chips_config.txt'}")
            print(f"  - Scenario: {PROJECT_ROOT / 'input.txt'}")
            print("\nYou can now run: ./start.ps1 (or ./start.sh on Unix)")
            print("to start ahoy and the other agents.\n")
        else:
            print("\n❌ Setup failed. Some files could not be written.")
            sys.exit(1)
    
    async def _ask_for_additional_roles(self, roles_list: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """Ask user if they want to add more roles for multi-protocol support."""
        print(f"\n{'='*70}")
        print("Multi-Protocol Support")
        print(f"{'='*70}")
        print(f"\nCurrent roles: {', '.join([f'{p}:{r}' for p, r in roles_list])}")
        
        while True:
            response = input("\nWould you like to add another protocol/role? (yes/no): ").strip().lower()
            if response in ('no', 'n'):
                break
            elif response in ('yes', 'y'):
                protocol, role = self.show_protocol_options()
                if (protocol, role) not in roles_list:
                    roles_list.append((protocol, role))
                    print(f"✓ Added {protocol}:{role}")
                    print(f"  Current roles: {', '.join([f'{p}:{r}' for p, r in roles_list])}")
                else:
                    print(f"⚠ {protocol}:{role} already in list")
            else:
                print("Please enter 'yes' or 'no'.")
        
        return roles_list
    
    def _confirm_all_selections(self) -> bool:
        """Confirm all selected roles."""
        print(f"\n{'='*70}")
        print("Configuration Summary")
        print(f"{'='*70}")
        for i, (protocol, role) in enumerate(self.roles_list, 1):
            print(f"{i}. {protocol}:{role}")
        print(f"\nScenario:\n{self.conversation}\n")
        
        while True:
            response = input("Is this correct? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            else:
                print("Please enter 'yes' or 'no'.")


if __name__ == "__main__":
    chips = CHIPS()
    asyncio.run(chips.run())
