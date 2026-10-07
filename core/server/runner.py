"""Core server runner and background process entrypoint.

Runs the local WebSocket server on 127.0.0.1:8765.
"""

import asyncio
import signal
import sys
from typing import Any

from core.logger import get_logger
from core.server.server import AGEServer

logger = get_logger("server.runner")


def main() -> None:
    """Run AGE Core server."""
    logger.info("Initializing AGE Core Server runner...")
    server = AGEServer()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def _shutdown(signum: int, frame: Any) -> None:
        logger.info("Shutdown signal received (%s). Stopping server...", signum)
        loop.create_task(server.stop())
        sys.exit(0)

    try:
        signal.signal(signal.SIGINT, _shutdown)
        signal.signal(signal.SIGTERM, _shutdown)
    except (ValueError, AttributeError):
        pass

    try:
        loop.run_until_complete(server.serve_forever())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Server runner exited cleanly.")
    finally:
        loop.close()


if __name__ == "__main__":
    main()
