#!/usr/bin/env python3
"""
Entry point for running as module: python -m bot
"""

import sys
import asyncio

from bot.app import main


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass
