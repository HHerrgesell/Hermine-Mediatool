#!/usr/bin/env python3
"""Entry point for running as module."""

if __name__ == "__main__":
    from src.main import main
    import asyncio
    asyncio.run(main())
