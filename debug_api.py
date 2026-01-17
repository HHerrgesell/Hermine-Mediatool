#!/usr/bin/env python3
"""Debug script to inspect API responses"""
import json
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

from src.config import Config
from src.api.hermine_client import HermineClient

def main():
    # Load config
    config = Config()

    # Create client
    client = HermineClient(
        config.hermine.base_url,
        config.hermine.username,
        config.hermine.password
    )

    # Get first few messages from the channel
    channel_id = config.target_channels[0] if config.target_channels else "259009"

    print(f"\n🔍 Fetching messages from channel {channel_id}...")

    data = client._post("message/content", {
        "channel_id": channel_id,
        "source": "channel",
        "limit": 5,
        "offset": 0,
    })

    messages = data.get("messages", [])
    print(f"\n✓ Found {len(messages)} messages")

    if messages:
        print("\n" + "="*80)
        print("FIRST MESSAGE STRUCTURE:")
        print("="*80)
        msg = messages[0]
        print(json.dumps(msg, indent=2, default=str))

        print("\n" + "="*80)
        print("MESSAGE KEYS:")
        print("="*80)
        for key in msg.keys():
            print(f"  - {key}: {type(msg[key]).__name__}")

        # Check for files
        if "files" in msg:
            print("\n" + "="*80)
            print("FILES FIELD:")
            print("="*80)
            print(json.dumps(msg["files"], indent=2, default=str))
        else:
            print("\n⚠️  No 'files' field in message!")

        # Check all messages for files
        files_count = 0
        for i, msg in enumerate(messages):
            files = msg.get("files", [])
            if files:
                files_count += len(files)
                print(f"\n✓ Message {i+1} has {len(files)} file(s)")
                for f in files:
                    print(f"  - {f.get('name', 'NO NAME')}: {f.get('type', 'NO TYPE')}")

        if files_count == 0:
            print("\n⚠️  No files found in any of the first 5 messages")
            print("    This might mean:")
            print("    1. Messages don't have attached files")
            print("    2. Files are in a different field")
            print("    3. Files require decryption first")

if __name__ == "__main__":
    main()
