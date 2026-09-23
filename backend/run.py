"""Standalone launcher for the packaged EXE.

Starts the API + bundled UI on a local port and opens the default browser.
Run configuration comes from the UI (AWS accounts) and the local AWS credential
chain — no secrets are baked into the executable.
"""
from __future__ import annotations

import os
import threading
import webbrowser

import uvicorn

from app.config import settings
from app.main import app

HOST = os.getenv("DASHBOARD_HOST", "127.0.0.1")
PORT = int(os.getenv("DASHBOARD_PORT", "8000"))


def _open_browser() -> None:
    webbrowser.open(f"http://{HOST}:{PORT}/")


def main() -> None:
    # Delay slightly so the server is listening before the browser opens.
    threading.Timer(1.5, _open_browser).start()
    print(f"DevOps Intelligence Dashboard running at http://{HOST}:{PORT}")
    print(f"Data & configuration stored in: {settings.DATA_DIR}")
    print("Press Ctrl+C to stop.")
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
