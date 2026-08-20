"""Container healthcheck.

Run as `python -m app.healthcheck`. Implemented in Python rather than curl so the
runtime image does not have to ship an HTTP client it would otherwise never need
— one fewer binary in the image is one fewer thing to scan and patch.
"""

from __future__ import annotations

import sys
import urllib.error
import urllib.request

URL = "http://127.0.0.1:8000/v1/health/live"
TIMEOUT_SECONDS = 3


def main() -> int:
    try:
        with urllib.request.urlopen(URL, timeout=TIMEOUT_SECONDS) as response:
            return 0 if response.status == 200 else 1
    except (urllib.error.URLError, OSError, ValueError):
        return 1


if __name__ == "__main__":
    sys.exit(main())
