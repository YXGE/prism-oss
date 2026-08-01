"""Fast local/CI smoke checks that do not start a listening server."""

from __future__ import annotations

import os
import sys
import tempfile
import warnings
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

with tempfile.TemporaryDirectory(prefix="prism-check-") as temp_dir:
    os.environ.setdefault("DASHBOARD_PASSWORD", "local-check-password-000000000000")
    os.environ["PRISM_DATA_DIR"] = str(Path(temp_dir) / "data")
    os.environ["PRISM_INBOX_DIR"] = str(Path(temp_dir) / "inbox")

    warnings.filterwarnings(
        "ignore",
        message=r"Using `httpx` with `starlette\.testclient` is deprecated.*",
    )
    from fastapi.testclient import TestClient
    import server

    with TestClient(server.app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200, health.text
        payload = health.json()
        assert payload["ok"] is True
        assert {"version", "commit", "build_time"} <= payload.keys()

        expected = {
            "/": "text/html",
            "/manifest.webmanifest": "application/manifest+json",
            "/sw.js": "application/javascript",
        }
        for path, media_type in expected.items():
            response = client.get(path)
            assert response.status_code == 200, f"{path}: {response.status_code}"
            assert media_type in response.headers.get("content-type", ""), path

        assert client.get("/api/sessions").status_code == 401

print("runtime smoke checks passed")
