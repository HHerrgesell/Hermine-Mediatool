#!/usr/bin/env python3
"""Fetch and analyze the ServiceWorker to understand file download mechanism"""

import requests
import re

def main():
    sw_url = "https://app.thw-messenger.de/thw/sw.js"

    print("\n" + "="*80)
    print("SERVICE WORKER ANALYSIS")
    print("="*80)

    print(f"\nFetching ServiceWorker from: {sw_url}")

    try:
        response = requests.get(sw_url, verify=True)
        response.raise_for_status()

        sw_code = response.text
        print(f"✓ ServiceWorker fetched ({len(sw_code)} bytes)")

        # Save full code
        with open('/tmp/sw.js', 'w') as f:
            f.write(sw_code)
        print(f"✓ Full code saved to /tmp/sw.js")

        # Look for fetch event handler
        print("\n" + "-"*80)
        print("LOOKING FOR FILE DOWNLOAD LOGIC")
        print("-"*80)

        # Search for fetch event
        fetch_patterns = [
            r"addEventListener\(['\"]fetch['\"]",
            r"onfetch\s*=",
            r"self\.addEventListener\(['\"]fetch['\"]",
        ]

        for pattern in fetch_patterns:
            if re.search(pattern, sw_code):
                print(f"\n✓ Found fetch event listener")
                break

        # Look for file-related logic
        file_keywords = [
            'file', 'download', 'stream', 'blob', 'response',
            'api.thw-messenger.de', 'app.thw-messenger.de',
            'message/content', '/file/'
        ]

        print("\n" + "-"*80)
        print("SEARCHING FOR RELEVANT CODE SECTIONS")
        print("-"*80)

        for keyword in file_keywords:
            matches = list(re.finditer(re.escape(keyword), sw_code, re.IGNORECASE))
            if matches:
                print(f"\n'{keyword}': {len(matches)} occurrences")

                # Show context around first match
                if len(matches) > 0:
                    match = matches[0]
                    start = max(0, match.start() - 100)
                    end = min(len(sw_code), match.end() + 100)
                    context = sw_code[start:end]
                    print(f"  First context: ...{context}...")

        # Look for API endpoints
        print("\n" + "-"*80)
        print("LOOKING FOR API ENDPOINTS")
        print("-"*80)

        # Find all URLs/paths
        url_pattern = r'["\']/((?:api|file|message|download)[^"\']*)["\']'
        urls = re.findall(url_pattern, sw_code)

        if urls:
            unique_urls = sorted(set(urls))
            print(f"\nFound {len(unique_urls)} unique API paths:")
            for url in unique_urls:
                print(f"  /{url}")

        # Look for POST requests
        print("\n" + "-"*80)
        print("LOOKING FOR POST/FETCH CALLS")
        print("-"*80)

        post_pattern = r'(fetch|post|get)\s*\([^)]{0,200}\)'
        posts = re.findall(post_pattern, sw_code, re.IGNORECASE)

        if posts:
            print(f"\nFound {len(posts)} fetch/post calls")
            for i, post in enumerate(posts[:5]):  # Show first 5
                print(f"\n  {i+1}. {post}")

        print("\n" + "="*80)
        print("ANALYSIS COMPLETE")
        print("="*80)
        print("\n💡 Examine /tmp/sw.js manually to find the exact download logic")
        print("\n")

    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
