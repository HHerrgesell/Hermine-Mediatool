#!/usr/bin/env python3
"""Test script to analyze file download mechanism"""

import json
from src.api import HermineClient
from src.config import Config

def main():
    config = Config()
    client = HermineClient(
        base_url=config.hermine.base_url,
        username=config.hermine.username,
        password=config.hermine.password
    )

    print("\n" + "="*80)
    print("FILE ANALYSIS TEST")
    print("="*80)

    # Get messages from channel
    channel_id = "259009"
    print(f"\nFetching messages from channel {channel_id}...")

    try:
        data = client._post("message/content", {
            "channel_id": channel_id,
            "source": "channel",
            "limit": 1,
            "offset": 0,
        })

        print(f"\n✓ Response received")
        print(f"  Top-level keys: {list(data.keys())}")

        messages = data.get("messages", [])
        print(f"\n  Messages count: {len(messages)}")

        if messages:
            msg = messages[0]
            print(f"\n  Message keys: {list(msg.keys())}")

            files = msg.get("files", [])
            print(f"\n  Files in message: {len(files)}")

            if files:
                for idx, file_info in enumerate(files):
                    print(f"\n  --- File {idx + 1} ---")
                    print(f"  ID: {file_info.get('id')}")
                    print(f"  Name: {file_info.get('name')}")
                    print(f"  Mime: {file_info.get('mime')}")
                    print(f"  Size (advertised): {file_info.get('size_byte')} bytes")
                    print(f"  Encrypted: {file_info.get('encrypted')}")

                    # Check for various ID fields
                    print(f"\n  All ID-like fields:")
                    for key in file_info.keys():
                        if 'id' in key.lower():
                            print(f"    {key}: {file_info[key]}")

                    # Check for URL fields
                    print(f"\n  All URL-like fields:")
                    for key in file_info.keys():
                        if 'url' in key.lower() or 'path' in key.lower() or 'link' in key.lower():
                            print(f"    {key}: {file_info[key]}")

                    # Check embedded data size
                    base64_data = file_info.get('base_64', '')
                    if base64_data:
                        actual_size = len(bytes.fromhex(base64_data))
                        advertised_size = int(file_info.get('size_byte', 1))
                        print(f"\n  Embedded data (base_64 field):")
                        print(f"    Hex string length: {len(base64_data)}")
                        print(f"    Decoded bytes: {actual_size}")
                        print(f"    Ratio to advertised size: {actual_size / advertised_size * 100:.1f}%")

                    # Check keys structure
                    keys = file_info.get('keys', [])
                    if keys:
                        print(f"\n  Keys structure:")
                        print(f"    Keys count: {len(keys)}")
                        if keys:
                            print(f"    Keys[0] fields: {list(keys[0].keys())}")

                    # Show all fields for complete picture
                    print(f"\n  All fields in file object:")
                    for key in sorted(file_info.keys()):
                        value = file_info[key]
                        if isinstance(value, str) and len(value) > 100:
                            print(f"    {key}: <string, {len(value)} chars>")
                        elif isinstance(value, list):
                            print(f"    {key}: <list, {len(value)} items>")
                        elif isinstance(value, dict):
                            print(f"    {key}: <dict, {len(value)} keys>")
                        else:
                            print(f"    {key}: {value}")

                # Save full response to file for detailed analysis
                with open('/tmp/file_response.json', 'w') as f:
                    json.dump(data, f, indent=2, ensure_ascii=False)
                print(f"\n✓ Full response saved to /tmp/file_response.json")

        print("\n" + "="*80)
        print("TEST COMPLETE")
        print("="*80 + "\n")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
