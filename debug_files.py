#!/usr/bin/env python3
"""Debug script to inspect file fields"""
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

    # Get messages from the channel
    channel_id = config.target_channels[0] if config.target_channels else "259009"

    print(f"\n🔍 Fetching messages from channel {channel_id}...")

    data = client._post("message/content", {
        "channel_id": channel_id,
        "source": "channel",
        "limit": 50,
        "offset": 0,
    })

    messages = data.get("messages", [])
    print(f"\n✓ Found {len(messages)} messages")

    # Find first message with files
    for msg in messages:
        files = msg.get("files", [])
        if files:
            print("\n" + "="*80)
            print("FIRST FILE STRUCTURE:")
            print("="*80)
            file_info = files[0]
            print(json.dumps(file_info, indent=2, default=str))

            print("\n" + "="*80)
            print("FILE KEYS:")
            print("="*80)
            for key in file_info.keys():
                value = file_info[key]
                print(f"  - {key}: {type(value).__name__} = {value if not isinstance(value, (dict, list)) else '...'}")
            break
    else:
        print("\n⚠️  No files found in first 50 messages")

if __name__ == "__main__":
    main()
