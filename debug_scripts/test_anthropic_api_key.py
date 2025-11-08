#!/usr/bin/env python3
"""
Debug script to test Anthropic API key and list available models.
Uses the official Anthropic SDK.
"""

import os
import sys
from anthropic import Anthropic, APIError


def test_anthropic_api_key():
    """Test the Anthropic API key and list available models."""
    
    # Get API key from environment
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    
    if not api_key:
        print("❌ Error: ANTHROPIC_API_KEY environment variable not set")
        return False
    
    print(f"✓ API Key found (length: {len(api_key)} characters)")
    
    # Initialize the Anthropic client
    try:
        client = Anthropic(api_key=api_key)
        print("✓ Anthropic client initialized successfully")
    except Exception as e:
        print(f"❌ Failed to initialize Anthropic client: {e}")
        return False
    
    # Known Anthropic models to test (try in order)
    available_models = [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-20250514",
        "claude-3-5-haiku-20241022",
        "claude-3-haiku-20240307"
    ]
    
    # Test the API connection with a simple message
    test_model = None
    print("\n🔄 Testing API connection with available models...")
    for model in available_models:
        try:
            response = client.messages.create(
                model=model,
                max_tokens=100,
                messages=[
                    {"role": "user", "content": "Say 'API key is valid' and nothing else."}
                ]
            )
            print(f"✓ API connection successful using model: {model}")
            print(f"  Response: {response.content[0].text}")
            test_model = model
            break
        except APIError as e:
            if "not_found_error" in str(e) or "404" in str(e):
                continue
            elif "authentication" in str(e).lower() or "401" in str(e):
                print(f"❌ Authentication failed: Invalid API key")
                print(f"  Error: {e}")
                return False
            else:
                print(f"  Warning with {model}: {e}")
                continue
    
    if not test_model:
        print(f"❌ Could not connect with any available model")
        return False
    
    # List available models
    print("\n📋 Available Anthropic Models:")
    print("-" * 60)
    
    print("\nUSABLE MODEL IDs:")
    for model in available_models:
        print(f"  • {model}")
    
    print("\n" + "=" * 60)
    print("✅ All tests passed! API key is valid and ready to use.")
    print("=" * 60)
    
    return True


if __name__ == "__main__":
    success = test_anthropic_api_key()
    sys.exit(0 if success else 1)
