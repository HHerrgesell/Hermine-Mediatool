#!/usr/bin/env python3
"""Quick test to check if multipart form-data works"""

from src.api import HermineClient
from src.config import Config

config = Config()
client = HermineClient(
    base_url=config.hermine.base_url,
    username=config.hermine.username,
    password=config.hermine.password
)

file_id = '18192733'

print("\n" + "="*80)
print("MULTIPART FORM-DATA TEST")
print("="*80)

print(f"\nClient credentials:")
print(f"  device_id: {client.device_id}")
print(f"  client_key: {client.client_key[:20] if client.client_key else 'None'}...")

print(f"\nTesting /file/download with multipart/form-data...")
print(f"  File ID: {file_id}")

download_url = f"{client.base_url}/file/download?id={file_id}"
print(f"  URL: {download_url}")

form_data = {
    'client_key': client.client_key,
    'device_id': client.device_id,
}

print(f"\nForm data:")
for key, value in form_data.items():
    if value:
        print(f"  {key}: {value[:20] if len(value) > 20 else value}...")
    else:
        print(f"  {key}: None")

try:
    response = client.session.post(
        download_url,
        data=form_data,
        timeout=client.timeout,
        verify=client.verify_ssl,
        headers={
            "Origin": "https://app.thw-messenger.de",
            "Referer": "https://app.thw-messenger.de/",
        }
    )

    print(f"\nResponse:")
    print(f"  Status: {response.status_code}")
    print(f"  Content-Length: {len(response.content)} bytes")
    print(f"  Content-Type: {response.headers.get('Content-Type')}")

    if response.status_code == 200:
        print(f"\n✓ SUCCESS! Downloaded {len(response.content)} bytes")

        # Check if it's encrypted binary data
        if len(response.content) > 0:
            first_bytes = response.content[:20]
            print(f"  First 20 bytes: {first_bytes.hex()}")
    else:
        print(f"\n✗ FAILED with status {response.status_code}")
        print(f"  Response text: {response.text[:500]}")

except Exception as e:
    print(f"\n✗ ERROR: {e}")
    import traceback
    traceback.print_exc()

print("\n" + "="*80 + "\n")
