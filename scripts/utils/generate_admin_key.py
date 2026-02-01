#!/usr/bin/env python3
"""
Generate a secure admin API key for WarmProspect Chatbot Platform.

This script generates a cryptographically secure random API key that can be used
as the ADMIN_API_KEY environment variable.

Usage:
    python scripts/utils/generate_admin_key.py
    python scripts/utils/generate_admin_key.py --length 64
    python scripts/utils/generate_admin_key.py --format hex
    python scripts/utils/generate_admin_key.py --format base64
"""

import secrets
import argparse
import base64


def generate_api_key(length: int = 32, format_type: str = "hex") -> str:
    """
    Generate a cryptographically secure API key.
    
    Args:
        length: Length of the key in bytes (default: 32 bytes = 64 hex chars)
        format_type: Output format - 'hex', 'base64', or 'urlsafe' (default: 'hex')
    
    Returns:
        A secure random API key string
    """
    # Generate random bytes
    key_bytes = secrets.token_bytes(length)
    
    if format_type == "hex":
        return key_bytes.hex()
    elif format_type == "base64":
        return base64.b64encode(key_bytes).decode('utf-8')
    elif format_type == "urlsafe":
        return base64.urlsafe_b64encode(key_bytes).decode('utf-8').rstrip('=')
    else:
        raise ValueError(f"Invalid format type: {format_type}. Use 'hex', 'base64', or 'urlsafe'")


def main():
    parser = argparse.ArgumentParser(
        description="Generate a secure admin API key for WarmProspect Chatbot Platform"
    )
    parser.add_argument(
        "--length",
        type=int,
        default=32,
        help="Length of the key in bytes (default: 32 bytes = 64 hex characters)"
    )
    parser.add_argument(
        "--format",
        type=str,
        default="hex",
        choices=["hex", "base64", "urlsafe"],
        help="Output format: hex (default), base64, or urlsafe"
    )
    parser.add_argument(
        "--env-format",
        action="store_true",
        help="Output in .env file format (ADMIN_API_KEY=...)"
    )
    
    args = parser.parse_args()
    
    # Generate the key
    api_key = generate_api_key(length=args.length, format_type=args.format)
    
    # Output the key
    if args.env_format:
        print(f"ADMIN_API_KEY={api_key}")
        print("\n# Add this line to your .env file")
    else:
        print("Generated Admin API Key:")
        print(api_key)
        print(f"\n# Add to your .env file as:")
        print(f"ADMIN_API_KEY={api_key}")


if __name__ == "__main__":
    main()
