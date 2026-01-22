#!/usr/bin/env python3
"""
CHIPS - Conversational Interface for Protocol and Input Setup
A minimal, interactive interface to configure ahoy's protocol and role,
and generate input.txt based on user conversation.
"""

import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from lib.protocol_discovery import get_all_protocols, get_protocol_structure


class CHIPS:
    """Conversational interface for protocol and role selection."""
    
    def __init__(self):
        self.protocol = None
        self.role = None
        self.conversation = []
        self.protocols = get_all_protocols()
    
    def print_welcome(self):
        """Display welcome message."""
        print("\n" + "="*70)
        print("CHIPS - Protocol & Role Configuration Interface")
        print("="*70)
        print("\nHello! I'm CHIPS. I'll help you configure ahoy for a multi-agent scenario.")
        print("Let's determine which protocol and role you'd like ahoy to play.\n")
    
    def select_protocol(self) -> str:
        """Let user select a protocol."""
        print("Available protocols:")
        protocol_list = list(self.protocols.keys())
        for i, proto in enumerate(protocol_list, 1):
            print(f"  {i}. {proto}")
        
        while True:
            try:
                choice = input("\nWhich protocol should ahoy participate in? (number or name): ").strip()
                
                # Try numeric choice
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(protocol_list):
                        return protocol_list[idx]
                
                # Try name match
                if choice in protocol_list:
                    return choice
                
                print(f"Invalid choice. Please enter a number 1-{len(protocol_list)} or a protocol name.")
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                sys.exit(0)
    
    def select_role(self, protocol: str) -> str:
        """Let user select a role for the protocol."""
        structure = get_protocol_structure(protocol)
        if not structure or not structure.get("roles"):
            print(f"Could not find roles for protocol: {protocol}")
            return None
        
        roles = structure["roles"]
        print(f"\nAvailable roles in {protocol}:")
        for i, role in enumerate(roles, 1):
            print(f"  {i}. {role}")
        
        while True:
            try:
                choice = input(f"\nWhich role should ahoy play in {protocol}? (number or name): ").strip()
                
                # Try numeric choice
                if choice.isdigit():
                    idx = int(choice) - 1
                    if 0 <= idx < len(roles):
                        return roles[idx]
                
                # Try name match
                if choice in roles:
                    return choice
                
                print(f"Invalid choice. Please enter a number 1-{len(roles)} or a role name.")
            except KeyboardInterrupt:
                print("\nSetup cancelled.")
                sys.exit(0)
    
    def gather_requirements(self) -> str:
        """Gather user requirements/goals for the scenario."""
        print(f"\n{'='*70}")
        print(f"Scenario Configuration for {self.protocol}:{self.role}")
        print(f"{'='*70}")
        print("\nDescribe the scenario and requirements for ahoy in this role.")
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
        
        requirements = "\n".join(lines).strip()
        return requirements if requirements else "Execute the protocol successfully."
    
    def confirm_setup(self) -> bool:
        """Confirm the configuration before writing files."""
        print(f"\n{'='*70}")
        print("Configuration Summary")
        print(f"{'='*70}")
        print(f"Protocol: {self.protocol}")
        print(f"Role: {self.role}")
        print(f"Input:\n{self.conversation}\n")
        
        while True:
            response = input("Does this look correct? (yes/no): ").strip().lower()
            if response in ('yes', 'y'):
                return True
            elif response in ('no', 'n'):
                return False
            else:
                print("Please enter 'yes' or 'no'.")
    
    def write_role_file(self) -> bool:
        """Write the protocol:role config to temp file for ahoy to read."""
        try:
            role_file = Path(tempfile.gettempdir()) / "maf_chips_config.txt"
            role_file.write_text(f"{self.protocol}:{self.role}")
            print(f"✓ Config file written: {role_file}")
            return True
        except Exception as e:
            print(f"✗ Error writing config file: {e}")
            return False
    
    def write_input_file(self) -> bool:
        """Write the input.txt file with user requirements."""
        try:
            input_file = PROJECT_ROOT / "input.txt"
            input_file.write_text(self.conversation)
            print(f"✓ Input file written: {input_file}")
            return True
        except Exception as e:
            print(f"✗ Error writing input file: {e}")
            return False
    
    def run(self):
        """Run the CHIPS interface."""
        self.print_welcome()
        
        # Protocol selection
        self.protocol = self.select_protocol()
        print(f"✓ Selected protocol: {self.protocol}")
        
        # Role selection
        self.role = self.select_role(self.protocol)
        if not self.role:
            print("Failed to select a role. Exiting.")
            sys.exit(1)
        print(f"✓ Selected role: {self.role}")
        
        # Gather requirements
        self.conversation = self.gather_requirements()
        
        # Confirm setup
        while not self.confirm_setup():
            print("\nLet's try again.\n")
            self.protocol = self.select_protocol()
            self.role = self.select_role(self.protocol)
            self.conversation = self.gather_requirements()
        
        # Write files
        print(f"\n{'='*70}")
        print("Writing configuration files...")
        print(f"{'='*70}\n")
        
        config_ok = self.write_role_file()
        input_ok = self.write_input_file()
        
        if config_ok and input_ok:
            print(f"\n{'='*70}")
            print("✅ Setup complete!")
            print(f"{'='*70}")
            print(f"\nConfiguration saved for {self.protocol}:{self.role}")
            print(f"  - Protocol/Role: {Path(tempfile.gettempdir()) / 'maf_chips_config.txt'}")
            print(f"  - Requirements: {PROJECT_ROOT / 'input.txt'}")
            print("\nYou can now run: ./start.ps1 (or ./start.sh on Unix)")
            print("to start ahoy and the other agents.\n")
        else:
            print("\n❌ Setup failed. Some files could not be written.")
            sys.exit(1)


if __name__ == "__main__":
    chips = CHIPS()
    chips.run()
